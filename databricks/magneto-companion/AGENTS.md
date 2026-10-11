# Magneto companion agent development

Read AGENTKIT_CONTRACT.md before editing runtime integration. This is a stateless, single-node LangGraph
plan service, using full companion snapshots and Agent Bricks custom-server deployment. Run
`uv run pytest` in this directory.

Never execute a tool or grade a response here: the harness owns physical actions and the deterministic
comparison. Never claim a snapshot's device is connected when it is not.

## Shared component contracts

- Read [../contracts/README.md](../contracts/README.md) before changing a cross-component interface. It is
  the authoritative v1 baseline; schemas/examples live beside it.
- The companion boundary is additive: `companion-snapshot`, `companion-tool-plan`, `companion-outcome`.
  Preserve the deployed director demo wire format and the existing `decision`/`session-snapshot` payloads.
- Run `npm run check:contracts` from the repository root for contract changes. Update producer, consumer,
  examples and migration notes together for a new version.

## Future learner reflection

Read `../../docs/about-me-intelligence-handoff.md` before implementing post-session insight conversion, MLflow evidence retrieval, learner memory or update epochs. This is accepted product context, not an implemented service or a replacement for the v1 contracts. Preserve the stateless bounded planner; proposed reflection is a separate read-only step.
