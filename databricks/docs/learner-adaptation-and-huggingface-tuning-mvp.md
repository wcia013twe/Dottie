# Learner adaptation and Hugging Face tuning MVP

Status: proposed implementation workflow, October 11, 2026. Start with structured learning evidence, versioned learner intelligence, and prompt optimization. Add a small Hugging Face weight-tuning experiment after establishing a reliable evaluation set. Training changes shared teaching behavior; personal facts remain in revisable learner profiles.

This workflow preserves the local browser, existing demo interfaces, and the Orin harness's ownership of physical effects. It does not authorize GPU provisioning, training, uploading learner data, or replacing the deployed model. The existing research pipeline prepares cited domain evidence; personal interaction analysis is a separate integration.

Read [the learner intelligence handoff](../../docs/about-me-intelligence-handoff.md) for accepted insight criteria and update epochs, and [the authoritative contracts](../contracts/README.md) before implementing new interfaces. An intelligence update epoch is a profile publication; a training epoch is a pass through a training dataset.

## MVP lesson and profile workflow

1. **Start a session with one profile revision.** Resolve the learner identity in application code. Supply the planner with the current task, session evidence, relevant profile facts, and available bounded tools. Preserve existing v1 contracts until an additive or versioned profile integration is defined.
2. **Select and validate one action.** The companion returns one tool plan. The harness validates it, executes the action, and records device acknowledgements separately from learner outcomes. The companion never executes tools or grades a learner.
3. **Save outcome evidence.** Record task/target, difficulty, support provided, independent versus supported/deferred response, timestamp, and teacher confirmation. Link outcomes to the preceding request/trace. Unconfirmed transcripts, device failures and synthetic fixtures cannot become progress evidence.
4. **Update after an explicitly ended or paused session.** A separate updater reads saved outcomes and linked decision traces, proposes a small number of observations, preferences or teaching hypotheses, and can return no new finding. Validate provenance and allowed fields before publishing a new profile revision. Keep the last successful revision on failure; handle retries idempotently.
5. **Use that revision in the next lesson.** Show concise actionable insights with expandable evidence. Allow corrections and removal. Start with one adaptation, such as prompt pause duration, and compare later independent performance at similar task difficulty.

An MVP is complete when an actual confirmed outcome can produce a traceable, reversible profile update that reaches the next session. A successful trace or a polished profile summary alone does not satisfy this criterion.

## MVP shared agent improvement workflow

Collect representative snapshots and teacher-reviewed acceptable plans into a versioned evaluation dataset. Include insufficient evidence, requests for help, device failures, supported answers, and invalid/stale actions. Split by learner and time where feasible so related sessions do not leak across training and held-out evaluation.

Register tunable teaching instructions in the MLflow Prompt Registry. Keep tool schemas, protocol validation, identity, permissions and physical limits in code outside the editable prompt. Separate evaluation code scores schema validity, allowed actions, evidence support and teacher-rated suitability; later independent performance measures learning benefit.

Use expert feedback to improve the evaluator, then run a bounded GEPA prompt search and evaluate the candidate on held-out cases. Promote only after meeting predeclared quality, latency and cost criteria, and retain the baseline for rollback. This follows the feedback, judge-alignment and prompt-optimization pattern in Databricks' [self-optimizing football chatbot](https://www.databricks.com/blog/self-optimizing-football-chatbot-guided-domain-experts-databricks). Agent output quality and learner benefit remain separate measurements.

## Hugging Face weight tuning process

1. **Confirm infrastructure and choose a candidate.** Check AI Runtime preview access, region, GPU capacity, model license/access and serving compatibility. Start with one small open model as an experimental candidate; record its Hugging Face repository and immutable revision. Establish its untuned baseline on the same evaluation set.
2. **Prepare supervised examples.** The conceptual training pair is `validated snapshot + available tools -> teacher-approved plan`. This is a dataset design, not a new wire contract. Remove identifying content and exclude synthetic observations from claims about real learning. Model-generated plans become labels only after explicit review. Preserve dataset version, provenance, split and review policy.
3. **Run one supervised fine-tune on AI Runtime.** Reuse an official notebook with TRL/Unsloth and LoRA, or a small full-weight example. Log the base model revision, dataset/splits, environment, hyperparameters, seed, loss and checkpoints in MLflow. AI Runtime supplies managed GPU compute; the application supplies training logic and data.
4. **Evaluate the resulting candidate.** Compare the tuned model with its untuned base and the existing production model using the same held-out cases. Check action validity, evidence support, teacher suitability, latency and total serving cost. Lower training loss does not prove better teaching or learner mastery.
5. **Export deployable weights.** Save the tokenizer, chat template and model configuration with the checkpoint. For LoRA, retain the original adapter and base revision. Where compatible, merge adapter weights into a full checkpoint and re-evaluate the merged artifact before serving.
6. **Test inference and register.** Start vLLM in an AI Runtime GPU notebook, validate representative requests and memory usage, then log the weights and inference entrypoint in MLflow and register a candidate model version in Unity Catalog.
7. **Serve separately and compare.** Create a candidate Databricks Model Serving endpoint using the tested environment and command. Adapt its response into the existing validated planner interface. Test through the simulated harness first; deploy to live lessons only after evaluation and explicit rollout authorization. Preserve rollback to the current endpoint.

Databricks provides LoRA and full supervised fine-tuning notebooks, an end-to-end fine-tuning-and-serving example, and Ray Tune hyperparameter search. Reuse those before building a trainer or search engine. Start with one training configuration; add bounded sweeps only when evaluation justifies them. [AI Runtime LLM examples](https://docs.databricks.com/aws/en/machine-learning/ai-runtime/examples/gpu-llms)

The documented custom LLM serving route is Public Preview, needs serverless GPU compute and UC model-creation permissions, and requires logging from a GPU notebook with MLflow 3.12+ and SDK 0.102.0+. Registration uses `env_pack="databricks_model_serving"`. It supports an OpenAI-compatible inference server, subject to model fit, runtime and regional availability. Separate LoRA adapter serving is currently listed as forthcoming; do not assume adapter hot-swapping works. Serving is billed by GPU instance hours; idle shutdown causes cold starts. [Custom LLM serving](https://docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms)

Hugging Face documents merging compatible LoRA adapters with base weights. Quantization and architecture can affect merge support, so verify the exact model and PEFT configuration. [Hugging Face LoRA](https://huggingface.co/docs/peft/v0.21.0/package_reference/lora)

## Ownership and experiment organization

- **Orchestrator experiment:** live planning traces, profile revision used, model/prompt versions and timing.
- **Updater experiment:** separately tagged research operations, learner profile updates, prompt optimization and experimental weight-training runs. Use role/task tags and dataset/model IDs to distinguish them; a dedicated training experiment can be introduced later if needed.
- **Application evidence store:** authoritative learner events and profile revisions. MLflow is observability and evaluation infrastructure, not the only learner database.
- **Research pipeline:** original sources, reviewed findings and cited guidance. It does not infer individual learner progress from research papers.

Two experiments remain adequate for an MVP, while the processing tasks stay separate. Managed memory, Lakeflow Jobs and GPU services are possible later integrations; their availability and costs must be checked before use. The existing companion is stateless, and the learner-profile and tuning integrations described here are planned rather than deployed.
