# Story prompt optimization pilot

CLI integration is live. Deployed runtime alias activation is pending approval for the beta registry’s additional schema privileges; the app has been restored to its previous hardcoded prompt. The story director code can load `prompts:/workspace.magneto.story_orchestrator@champion` from the real Databricks MLflow Prompt Registry. Its immutable runtime boundary and strict six-field decision validator remain outside the tunable template. Registry failures are explicit; the service does not silently substitute a policy or override model decisions.

Enable runtime registry loading by setting `MAGNETO_PROMPT_URI=prompts:/workspace.magneto.story_orchestrator@champion` in `app.yaml` and redeploying only after its service identity has the required privileges.

The CLI uses native MLflow datasets, registered deterministic scorers, `mlflow.genai.evaluate`, and `GepaPromptOptimizer`. It calls the existing Qwen endpoint for both decisions and reflection. It changes prompts, not model weights.

## Run with the CLI

Use the existing authenticated `magneto` Databricks profile. Install `scripts/story_tuning/requirements.txt` into a tooling environment, separate from the serving app. Python 3.12 is recommended; Python 3.14 currently needs `WHENEVER_NO_BUILD_RUST_EXT=1` for the Databricks evaluation dependency.

```sh
.venv-agent/bin/python scripts/tune_story.py --max-metric-calls 36
```

The workflow reuses `/Shared/magneto-research` (ID `1306573313615572`) for optimization/evaluation and the existing director experiment for deployed runtime traces. It reuses existing datasets/scorers by name. The beta registry currently requires schema `CREATE FUNCTION`, `EXECUTE`, and `MANAGE` even to view prompts. The app startup check records access failures in MLflow and fails readiness; grant changes require explicit approval because they affect the entire schema. No credentials are saved in reports.

1. Load `champion`, or register the existing demo policy as the first baseline.
2. Make a real inference and verify its UC trace before evaluation.
3. Create/reuse `workspace.magneto.story_policy_synthetic_train_v1` (15 cases) and `workspace.magneto.story_policy_synthetic_heldout_v1` (27 cases).
4. Evaluate the baseline on held-out sequences. Run GEPA on training sequences with a bounded metric-call budget; keep the reflection step enabled even when the baseline scores perfectly, to demonstrate the optimizer.
5. Register the result as `candidate`, evaluate it on the same held-out set, and promote only a strict gain without regression, with perfect contract and policy checks. Save the previous champion before promotion.
6. Save the actual IDs and scores in `reports/story-tuning-live.json`. Also run the five existing fixtures through the live service after deployment.

Resume an interrupted search with `--resume` to reuse the verified smoke and held-out baseline. Reflection is limited to 1,200 output tokens and configured for a 60-second request timeout. GEPA checks its metric-call budget between iterations and can exceed it by one candidate validation batch. The metric-call budget applies to GEPA; baseline and candidate held-out evaluations and the smoke call add inference requests. This is a manually triggered CLI pipeline, not a scheduled continual optimizer. Repeat evaluations on a small set can overfit it; collect new reviewed cases for later iterations.

## What the checks establish

- `valid_decision`: model/transport succeeded and the existing validator accepted the decision.
- `teaching_policy`: action matches engineering labels derived from the existing demo policy.
- `concise_activity`: reason under 200 characters and teaching prompt under 160.

These are synthetic regression cases, not teacher-reviewed examples or learner outcomes. The held-out sequences are disjoint from training sequences, but all come from the same narrow demo policy. There is no learner-level generalization claim. No personal-intelligence updater, research retrieval, or production learning data is connected by this implementation. Add teacher suitability and delayed independent performance checks when reviewed evidence is available; these checks do not prove educational benefit.

## Rollback

Use a verified earlier version (initial baseline is version 1):

```python
import mlflow
mlflow.set_tracking_uri('databricks://magneto')
mlflow.set_registry_uri('databricks-uc')
mlflow.genai.set_prompt_alias('workspace.magneto.story_orchestrator', 'champion', 1)
```

The app resolves the alias at each decision. No framework, learner database, GPU hosting, or response wire-format change is introduced.
