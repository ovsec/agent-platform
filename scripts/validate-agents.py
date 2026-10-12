# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "jsonschema[format]>=4.23"]
# ///
"""Validate agent manifests: schemas/agent.schema.json plus the checks a schema can't express.

  uv run scripts/validate-agents.py test-agents/*/agent.yaml       # agent folders: agent.yaml (+ flow.json)
  uv run scripts/validate-agents.py --owners owners.yaml stage/*/agent.yaml prod/*/agent.yaml   # agent-catalog

Checks: schema; a langflow agent's flow.json exists, has the manifest's flow_id and no credential typed into a
password field; with --owners (agent-catalog), the folder is named after the slug and the release's source repo
owns the slug (release.yaml next to the manifest, written by the agent workflow).
Exit code 0 = all valid.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "schemas/agent.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)


def check_flow(path: Path, flow_id: str) -> list[str]:
    if not path.exists():
        return [f"flow not found: {path}"]
    flow = json.loads(path.read_text())
    errors = [] if flow.get("id") == flow_id else [f"{path}: id {flow.get('id')} != langflow.flow_id {flow_id}"]
    for node in flow.get("data", {}).get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        for field, spec in template.items():
            # credentials belong in Langflow global variables (load_from_db) or the gateway, never in the file
            if isinstance(spec, dict) and spec.get("password") and spec.get("value") and not spec.get("load_from_db"):
                errors.append(f"{path}: node {node.get('id')} field {field!r} has a credential in the flow")
    return errors


def check_owner(manifest: Path, slug: str, owners: dict) -> list[str]:
    release_file = manifest.parent / "release.yaml"
    if not release_file.exists():
        return [f"{manifest}: release.yaml missing"]
    repo = yaml.safe_load(release_file.read_text()).get("source_repo")
    allowed = owners.get(slug)
    if allowed is None:
        return [f"{slug}: not registered in owners.yaml (ask the platform team)"]
    return [] if repo == allowed else [f"{slug}: owned by {allowed}, not {repo}"]


def check(manifest: Path, owners: dict | None) -> list[str]:
    agent = yaml.safe_load(manifest.read_text())
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in VALIDATOR.iter_errors(agent)]
    if errors or not isinstance(agent, dict):
        return errors
    slug = agent["slug"]
    if agent["runtime"] == "langflow":
        errors += check_flow(manifest.parent / "flow.json", agent["langflow"]["flow_id"])
    if owners is not None:  # catalog: <env>/<slug>/ (agent repos may name their folders freely)
        if manifest.parent.name != slug:
            errors.append(f"slug {slug!r} does not match its folder {manifest.parent.name!r}")
        errors += check_owner(manifest, slug, owners)
    return errors


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("manifests", nargs="+", type=Path, help="agent.yaml files")
    p.add_argument("--owners", type=Path, help="owners.yaml (slug: org/repo) to enforce slug ownership")
    args = p.parse_args()
    manifests = args.manifests
    owners = yaml.safe_load(args.owners.read_text()) or {} if args.owners else None
    failed = 0
    for m in manifests:
        errors = check(m, owners)
        print(f"{'FAIL' if errors else 'ok  '} {m}")
        for e in errors:
            print(f"     {e}")
        failed += bool(errors)
    sys.exit(f"{failed} of {len(manifests)} agent(s) invalid" if failed else 0)


if __name__ == "__main__":
    main()
