# Fictional Story session audit

The browser walkthrough uses the normal Peter Rabbit reader and teacher coach on a separate localhost origin. No genuine learner outcome was invented or uploaded. The live model produced an introduction and then a continue proposal. A separately labeled controlled identification proposal exercised the saved-observation branch. Hardware remained disconnected; tactile confirmation was fictional test input.

Reproduce the isolated identification walkthrough:

```sh
python3 scripts/serve_story_test.py --identify-fixture
```

Open `http://127.0.0.1:8100/learn/?profile=synthetic-test#stories`, open Peter Rabbit, seek to chapter page 3, open Teacher coach, request a proposal, start the activity, confirm test material, speak the prompt, and record a fictional outcome. Never use the ordinary live server to record invented outcomes.

`telemetry.json` captures the test controller snapshot. `evidence.json` contains only the normalized identification observations, marked `synthetic:true`. Introduction and matching observations are excluded from identification evidence. The production controller itself still keeps sessions in memory; this test snapshot file does not add durable session restoration to production.

Run the saved batch through the existing isolated Databricks test path:

```sh
.venv-agent/bin/python scripts/test_synthetic_cloud_flow.py --evidence reports/storybook-session-test/evidence.json
```

The test writes only `workspace.magneto.synthetic_learner_e2e_v1`; it requires exact SQL readback, constrained Genie prose, deterministic metrics, schema validation and unchanged replay. It does not select the production learner. Inspect the run journal in `reports/synthetic-cloud-flow/`. The isolated server serves the matching cloud profile after publication; before that it serves the explicitly fictional local baseline.

Observed limits:

- Saving reading position survives reload, but does not save/resume the coach's anonymous session.
- Confirming an identification observation triggers the production pending evidence queue immediately. Closing/finishing the book has no separate session-finalization/profile-update trigger.
- The shelf's “Try Braille activities” button opens a labeled local mock flow, separate from the live coach and learner updater.
- Only identification has an automatic learner evidence adapter. Other categories remain insufficient without explicit normalized observations; unspecified difficulty prevents comparable-session trend claims.
- The live model's continue reason called the earlier introduction “recognition.” The deterministic adapter correctly excluded that introduction. Model explanations still need semantic review; successful transport does not validate learner claims.
- SQL → Genie → About me is tested with fictional data. Real outcomes, MLflow outcome joins, stable cross-session learner identity and planner memory readback remain separate requirements.
