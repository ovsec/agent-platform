#!/usr/bin/env bash
# Set up the GitHub side of the platform from .github/github.env (ORG, PLATFORM_TEAM, VISIBILITY).
# Run the steps in this order, each once; they are safe to repeat.
#
#   ./scripts/github-setup.sh check                      config, gh login and scopes
#   ./scripts/github-setup.sh platform                   ORG/agent-platform: create, push, protect main
#   ./scripts/github-setup.sh tag-v1                     point the v1 contract tag at origin/main (after merging)
#   ./scripts/github-setup.sh app <app-id> <key.pem>     org variable + secret for the release GitHub App
#   ./scripts/github-setup.sh catalog                    ORG/agent-catalog from templates/agent-catalog
#   ./scripts/github-setup.sh template                   ORG/agent-template from templates/agent-template
#   ./scripts/github-setup.sh new-agent-repo <repo> <team> <slug>...   onboard an agent team (from agent-template)
#   FROM_DIR=../my-agents ./scripts/github-setup.sh new-agent-repo my-agents finance-ops invoice-monitor ...
#                                                      same, pushing an existing local repo instead of the template
#
# Needs: gh logged in as an org admin with scopes repo, workflow, admin:org (gh auth refresh -s admin:org).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=/dev/null
source .github/github.env

die() { echo "error: $*" >&2; exit 1; }
[[ ${ORG:-ORG} != ORG ]] || die "set ORG in .github/github.env first"

# Replace the ORG placeholder (as in ORG/agent-platform or @ORG/team) in the given files.
render() { perl -pi -e "s#(?<![A-Za-z0-9_-])ORG/#${ORG}/#g" "$@"; }

# git over https with gh's login, without touching the global git config
ghgit() { git -c credential.helper= -c credential.helper='!gh auth git-credential' "$@"; }

repo_exists() { gh repo view "$ORG/$1" >/dev/null 2>&1; }

create_repo() {  # name description
  if repo_exists "$1"; then echo "$ORG/$1 exists"; return; fi
  gh repo create "$ORG/$1" "--$VISIBILITY" --description "$2"
  gh api -X PUT "orgs/$ORG/teams/$PLATFORM_TEAM/repos/$ORG/$1" -f permission=admin
}

protect_main() {  # repo required-review-count check-name...
  local repo=$1 reviews=$2; shift 2
  local checks='[]'; (( $# )) && checks=$(printf '%s\n' "$@" | jq -R . | jq -s .)
  jq -n --argjson checks "$checks" --argjson reviews "$reviews" '{
      required_status_checks: {strict: false, contexts: $checks},
      enforce_admins: false,
      required_pull_request_reviews: {required_approving_review_count: $reviews, require_code_owner_reviews: true},
      restrictions: null}' |
    gh api -X PUT "repos/$ORG/$repo/branches/main/protection" --input - >/dev/null
  echo "protected $ORG/$repo main (checks: $*)"
}

push_rendered() {  # template-dir repo
  local tmp; tmp=$(mktemp -d)
  cp -R "templates/$1/." "$tmp/"
  find "$tmp" -type f -not -name '.gitkeep' -print0 | xargs -0 perl -pi -e "s#(?<![A-Za-z0-9_-])ORG/#${ORG}/#g"
  git -C "$tmp" init -q -b main
  git -C "$tmp" add -A
  git -C "$tmp" commit -qm "Initial $2 from agent-platform templates/$1"
  if [[ -n $(gh api "repos/$ORG/$2/commits?per_page=1" --jq '.[0].sha' 2>/dev/null) ]]; then
    echo "$ORG/$2 already has commits: not pushing (update it by PR)"
  else
    ghgit -C "$tmp" push -q "https://github.com/$ORG/$2.git" main
    echo "pushed $ORG/$2"
  fi
  rm -rf "$tmp"
}

case "${1:-}" in
  check)
    echo "org=$ORG platform_team=$PLATFORM_TEAM visibility=$VISIBILITY"
    gh auth status 2>&1 | grep -E "Logged in|scopes"
    gh api "orgs/$ORG" --jq '"org: \(.login) (\(.plan.name // "plan hidden"))"'
    gh api "orgs/$ORG/memberships/$(gh api user --jq .login)" --jq '"your role: \(.role)"'
    gh api "orgs/$ORG/teams/$PLATFORM_TEAM" --jq '"team: \(.slug)"' || die "team $PLATFORM_TEAM not found in $ORG"
    ;;

  platform)
    render .github/CODEOWNERS
    if ! git diff --quiet -- .github/CODEOWNERS; then
      git commit -qm "CODEOWNERS: GitHub org $ORG" -- .github/CODEOWNERS && echo "committed CODEOWNERS for $ORG"
    fi
    create_repo agent-platform "Agent platform: gateway, portal, runtimes, agent contract"
    git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$ORG/agent-platform.git"
    ghgit push -u origin main "$(git branch --show-current)"
    # agent repos call .github/workflows/agent.yml from here
    gh api -X PUT "repos/$ORG/agent-platform/actions/permissions/access" -f access_level=organization
    protect_main agent-platform 1 "test agents and gateway config" portal langflow-adapter
    echo "next: open a PR for $(git branch --show-current) → main, merge it, then run: $0 tag-v1"
    ;;

  tag-v1)
    ghgit fetch -q origin main
    git tag -f v1 origin/main
    ghgit push -f origin v1
    echo "v1 → $(git rev-parse --short origin/main). Move it only for backwards-compatible contract changes."
    ;;

  app)
    [[ $# -eq 3 && -f $3 ]] || die "usage: $0 app <app-id> <private-key.pem>"
    gh variable set AGENT_CATALOG_APP_ID --org "$ORG" --visibility all --body "$2"
    gh secret set AGENT_CATALOG_APP_KEY --org "$ORG" --visibility all < "$3"
    echo "set AGENT_CATALOG_APP_ID and AGENT_CATALOG_APP_KEY on $ORG"
    ;;

  catalog)
    create_repo agent-catalog "What runs where: agent releases per environment (written by the agent workflow)"
    push_rendered agent-catalog agent-catalog
    gh repo edit "$ORG/agent-catalog" --enable-auto-merge --delete-branch-on-merge
    protect_main agent-catalog 0 validate
    ;;

  template)
    create_repo agent-template "Start here: template for a platform agent (Langflow or AG-UI code)"
    push_rendered agent-template agent-template
    gh repo edit "$ORG/agent-template" --template
    protect_main agent-template 1
    ;;

  new-agent-repo)
    [[ $# -ge 4 ]] || die "usage: $0 new-agent-repo <repo> <team> <slug>..."
    repo=$2 team=$3; shift 3
    team_id=$(gh api "orgs/$ORG/teams/$team" --jq .id) || die "team $team not found in $ORG"
    if repo_exists "$repo"; then
      echo "$ORG/$repo exists"
    elif [[ -n ${FROM_DIR:-} ]]; then
      render "$FROM_DIR/.github/workflows/agent.yml"
      if ! git -C "$FROM_DIR" diff --quiet; then git -C "$FROM_DIR" commit -qam "agent workflow: GitHub org $ORG"; fi
      gh repo create "$ORG/$repo" "--$VISIBILITY"
      ghgit -C "$FROM_DIR" push -q "https://github.com/$ORG/$repo.git" main
    else
      gh repo create "$ORG/$repo" "--$VISIBILITY" --template "$ORG/agent-template"
    fi
    gh api -X PUT "orgs/$ORG/teams/$team/repos/$ORG/$repo" -f permission=maintain
    gh api -X PUT "orgs/$ORG/teams/$PLATFORM_TEAM/repos/$ORG/$repo" -f permission=admin
    gh api -X PUT "repos/$ORG/$repo/environments/stage" >/dev/null
    # prod: a member of the team approves; only tags (v*) can be released there
    jq -n --argjson id "$team_id" '{reviewers: [{type: "Team", id: $id}],
        deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}}' |
      gh api -X PUT "repos/$ORG/$repo/environments/prod" --input - >/dev/null
    gh api "repos/$ORG/$repo/environments/prod/deployment-branch-policies" --jq '.branch_policies[].name' |
      grep -qx 'v\*' || gh api -X POST "repos/$ORG/$repo/environments/prod/deployment-branch-policies" \
        -f name='v*' -f type=tag >/dev/null
    sleep 3   # template repos are filled asynchronously; main must exist before it can be protected
    protect_main "$repo" 1 "agent / validate"
    # register the slugs for this repo in agent-catalog (platform team approves the PR)
    tmp=$(mktemp -d)
    gh repo clone "$ORG/agent-catalog" "$tmp" -- -q
    for slug in "$@"; do
      [[ $slug =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || die "invalid slug: $slug"
      grep -q "^$slug:" "$tmp/owners.yaml" && die "$slug is already registered: $(grep "^$slug:" "$tmp/owners.yaml")"
      echo "$slug: $ORG/$repo" >> "$tmp/owners.yaml"
    done
    git -C "$tmp" checkout -qb "owners/$repo"
    git -C "$tmp" commit -qam "owners: $* → $ORG/$repo ($team)"
    ghgit -C "$tmp" push -q origin "owners/$repo"
    (cd "$tmp" && gh pr create --title "Register $* for $ORG/$repo" --body "Team: @$ORG/$team")
    rm -rf "$tmp"
    echo "done: https://github.com/$ORG/$repo (merge the agent-catalog PR above to allow releases)"
    ;;

  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
