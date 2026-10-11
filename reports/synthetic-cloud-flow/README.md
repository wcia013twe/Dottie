# Isolated synthetic cloud flow

Run from the repository root:

```sh
.venv-agent/bin/python scripts/test_synthetic_cloud_flow.py
```

The runner writes seventeen fictional River observations to the separate fixed
`workspace.magneto.synthetic_learner_e2e_v1` table, checks exact SQL readback,
passes that readback to Genie MCP, validates constrained prose, and publishes
an isolated schema-valid profile. Counts stay deterministic (two independent
recognitions out of five comparable opportunities). Identical replay creates
no new epoch. Synthetic flags remain true throughout. The live learner table,
active learner pointer, local facts and existing mock preview are untouched.

`latest.json` is the stage journal; `profile.json` is the latest successful
publication. Per-run journals retain IDs and errors. Genie response handles,
including rejected proposals, are saved in the isolated local cache. A first
attempt was correctly rejected for an unsupported numeric claim; tightened
test instructions subsequently passed the unchanged validator.

Resume an existing run using its twelve-character ID:

```sh
.venv-agent/bin/python scripts/test_synthetic_cloud_flow.py --resume f038af38d9ea
```

The runner checks existing SQL rows before an uncertain insert. Genie resumes
the same response for the same baseline/prompt. A deliberate prompt correction
creates a new response; it does not relabel a rejected one as successful.

After starting `python3 scripts/serve.py --port 8099`, view:
`http://127.0.0.1:8099/learn/?profile=synthetic-test#intelligence`.
The read-only test endpoint refuses missing/failed/mismatched publications.
It does not trigger the live feed. This proves a synthetic SQL-to-profile
handoff, not real learner progress, planner memory readback, research approval,
physical readiness or full-suite completion.
