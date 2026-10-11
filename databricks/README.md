# Databricks workloads

Start here before changing cloud code. These workloads share a repository, not a deployment lifecycle.

For the proposed lesson/profile loop, prompt optimization, and Hugging Face weight tuning and serving process, read [Learner adaptation and Hugging Face tuning MVP](docs/learner-adaptation-and-huggingface-tuning-mvp.md). This is project planning context. The [story prompt optimization pilot](docs/story-prompt-optimization.md) documents the real MLflow CLI integration, evaluation checks, and remaining runtime permissions.

## Runtime harness and Personal Intelligence

The names in [PR #8 (Add Harness)](https://github.com/wcia013twe/magneto/pull/8)
and [PR #7 (Personal Intelligence)](https://github.com/wcia013twe/magneto/pull/7)
refer to different responsibilities. This checkout contains #8; #7 is a separate
proposal. The following describes the code in those PRs, not verified deployment.

**The runtime harness does the action.** `../orin-harness/` runs locally on the
Orin. It owns the lesson/session state, validates a proposed tool call, drives
the Braille cell and audio, receives responses, and records execution evidence.
It compares a response with the expected target deterministically; that match
does not establish learner mastery. Its offline dry run uses simulated devices
and a fixture brain.

**The companion chooses the next action.** `magneto-companion/` receives the
harness's current snapshot and returns one bounded tool plan. It never drives
hardware or grades a response. #8 calls this the "Personal Intelligence brain,"
but the code is currently a stateless planner. The harness can instead call a
foundation model directly; direct and companion modes are alternative backends
for the same planning step, not two brains running together.

**PR #7 adds learner memory.** It adds profile/event contracts, a browser outbox,
localhost upload routes, and Delta storage behind the director app. It does not
add a new decision-making agent. The director still decides from the supplied
demo snapshot; neither it nor the companion reads that stored history yet.
The harness's companion outcomes are also not uploaded to this store yet.

For example: the companion proposes "present C"; the harness shows C, listens,
and records what happened. A future memory adapter could save that event and
later supply relevant history to the planner. That adapter is a remaining
integration task, not an implemented connection.

Keep the existing browser/director demo working while integrating the Orin
path. Its `teach`/`continue` decision and the companion's tool plan are different
contracts. Unifying the PRs requires preserving both contract families and
shared platform changes, then defining profile identity, consent, outcome
mapping, upload acknowledgement and history readback together. Merely merging
the branches will not create personalized decisions. Research produces future
cited teaching guidance; it remains separate from learner memory and device
execution.

| Directory | Owner/responsibility | Deployment |
| --- | --- | --- |
| `platform/` | Shared service wiring; existing namespace, references volume, director access and tracing setup | Explicit Python CLI; see its README |
| `magneto-director/` | Live teaching decisions and Agent Bricks runtime | Existing Agent Bricks deployment |
| `research-pipeline/` | Versioned research evidence, managed document processing, advisory judging, and cited domain search | Separate bundle; manual smoke/processing jobs and CLI |

## Base contracts

Read [contracts/README.md](contracts/README.md) before changing component interfaces. Versioned JSON Schemas and examples are the shared baseline for research, AI Search, the director, and the local runtime. Validate with `npm run check:contracts` from the repository root.

## Service map

### Architecture flow

The solid arrows show the implemented decision loop. Dashed arrows show shared configuration or future research integration, as labeled.

```mermaid
flowchart TD
    A["1. Local browser story demo<br/>Passage + complete session snapshot"] --> B["2. Local Python bridge<br/>POST /api/decision"]
    B -->|Authenticated invocation| C

    subgraph DB["Databricks"]
        C["3. Learning director in Databricks Apps<br/>Single-node LangGraph · stateless API"]
        C -->|One model call per decision| D["4. Foundation model endpoint<br/>Qwen · configurable"]
        D -->|Structured response| C
        C --> E["5. Decision validation<br/>continue or teach + evidence summary"]
        C -->|Context, output and timing| H["8. MLflow tracing<br/>Experiment + Unity Catalog trace tables"]
        I["9. References volume<br/>workspace.magneto.references"] -->|Explicit PDF intake| J["10. Research evidence pipeline<br/>Managed AI Functions + AI Search"]
        J -.->|Future curated guidance · not connected| C
    end

    E -->|Validated decision via bridge| F["6. Browser activity executor<br/>Continue story or simulate Braille activity"]
    F --> G["7. Teacher response<br/>Correct / Incorrect / Help · save locally"]
    G -->|Next passage + updated snapshot| A

    K["11. Shared platform wiring<br/>services.toml + authenticated adapters"] -.->|Configuration and transport| B
    K -.->|Configuration and transport| C
```

1. **Local browser story demo:** Supplies approved teacher passage summaries, the upcoming learning opportunity, labeled synthetic starting history, test props, and recorded session events. Original story content is never replaced by model output; imported books are not uploaded automatically.
2. **Local Python bridge:** Runs alongside the static site through `python3 scripts/serve.py`. It validates browser requests, authenticates with the local `magneto` profile, and invokes the deployed app. Credentials stay out of browser JavaScript.
3. **Learning director:** Runs natively in Databricks Apps using Agent Bricks' custom-server deployment. Its single-node LangGraph processes a complete snapshot on every request, without implicit conversational memory or a Lakebase learner database.
4. **Foundation model endpoint:** Currently uses `databricks-qwen3-next-80b-a3b-instruct`. One model call selects whether to continue or teach based on the supplied evidence. The endpoint is configurable; local code does not force the educational outcome.
5. **Decision validation:** Checks the action, passage, target letter, prompt, explanation, and learner-event reference before execution. Invalid output is rejected. A timeout or manual skip is never presented as an agent decision.
6. **Browser activity executor:** Applies the validated action while preserving the story. It currently displays explicitly simulated Braille and shows the explanation and timing in developer details. ElevenLabs teaching audio, physical servo acknowledgement, and camera observations are not connected to this decision loop yet.
7. **Teacher response:** Saves Correct, Incorrect, or Help before requesting the next decision. Connected-demo events use separate browser-local storage; existing books, reading positions, learning progress, and saved CAD designs remain separate. Request/session checks discard outdated responses.
8. **MLflow tracing:** Records the full decision context, returned output, model, request ID, timing, and execution spans. The active experiment is `/Shared/agentbricks_traces/magneto-director-uc`; its trace tables are in `workspace.magneto`. The existing SQL warehouse supports trace setup and readback. The earlier artifact-backed experiment is preserved.
9. **References volume:** Holds explicitly uploaded reference files under `/Volumes/workspace/magneto/references`. It is a source-storage location, not an implemented retrieval system; reference files do not automatically influence decisions.
10. **Research evidence pipeline:** Provides explicit PDF intake, managed parsing/preparation/extraction, review and provenance records, advisory MLflow judging, and cited AI Search across teaching and industry collections. Internal library retrieval is operational; approved teaching export preserves v1. An opt-in approved-guidance director adapter is implemented and tested locally; deployed activation and a live cited decision remain pending. See [verified behavior and limits](research-pipeline/docs/verification.md).
11. **Shared platform wiring:** `platform/services.toml` and `platform/magneto_platform/` define resource addresses, authenticated model/agent adapters, reference uploads, health checks, and tracing setup. The browser bridge and director use these shared adapters; `scripts/prepare_agent.py` packages a copy for deployment.

### Databricks service roles

- Lakehouse: original sources, structured evidence, review history, and derived search records.
- Unity Catalog: names, ownership and access for those assets.
- MLflow: separate director and research experiments; research operations and evidence assessments are traced.
- Agent Bricks: existing director consumes context; the new approved-research context path is opt-in and locally tested, with live activation pending.
- AI Search: research-owned hybrid index `workspace.magneto.research_index`; broad library, reviewed findings, and approved implications stay distinct.

`platform/services.toml` records existing shared resources. The research bundle references existing resources and must not also provision them. It owns its research tables, endpoint/index, experiment and manual jobs, while reusing shared namespaces and the reference volume. Resource existence in configuration is not proof of current access.

## Source of truth

Edit shared adapters in `platform/magneto_platform/`. The director's `magneto_platform/` and `services.toml` are deployment copies generated by `scripts/prepare_agent.py` at the repository root. Do not edit those copies manually. Preserve existing runtime paths and localhost bridges.

The research package uses the Databricks SDK for read-only smoke checks and explicit research operations. It does not provision shared namespaces or alter director-specific wiring. See its README for operational commands and permissions.

## Command boundaries

- Research tests, bundle validation and smoke checks: local validation/read-only metadata access.
- Research `bundle deploy`: writes a job and workspace files; does not run processing.
- Research `bundle run`: starts compute for the manual smoke job.
- Platform `provision` / `wire-app`: create resources or modify grants.
- Director deploy: changes the live application.

See each package's README before running mutating commands. Shared guidance/retrieval boundaries are defined in `contracts/`; internal extraction objectives, analysis methods and physical table/index layouts remain open.
