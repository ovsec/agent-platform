## What and why


## Checklist
- [ ] Agent changes: `access.roles` reviewed (who gets access?)
- [ ] Gateway or auth changes: `uv run scripts/e2e.py` passes on the local stack
- [ ] Contract changes (`schemas/agent.schema.json`, `.github/workflows/agent.yml`): backwards compatible, or a new
      major tag (`v2`) with a migration note for agent teams
