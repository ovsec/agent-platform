# agent-catalog

What runs where. One folder per released agent and environment, written only by the agent workflow
(`ORG/agent-platform/.github/workflows/agent.yml`), never by hand:

```
stage/<slug>/agent.yaml     manifest (schemas/agent.schema.json in agent-platform)
stage/<slug>/flow.json      Langflow agents
stage/<slug>/release.yaml   source repo, commit, who released it, workflow run, image for code agents
prod/<slug>/...
owners.yaml                 slug → the only repo allowed to release it (platform team)
```

- Release PRs auto-merge when `validate` passes: schema, flow and ownership.
- History of this repo = release history. Roll back from the agent repo (Actions → agent → Run workflow on
  an older tag), not by reverting here.
- New agent team or slug: the platform team runs `scripts/github-setup.sh new-agent-repo` in agent-platform.
