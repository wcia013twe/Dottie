# Research-owned evidence architecture

```text
Explicit PDF intake → existing reference volume + source registry
                    → ai_parse_document → saved parsed artifact
                    → ai_prep_search → original passages + enriched embedding text
                    → Delta search table → managed embeddings + hybrid AI Search

Original passage → ai_extract candidate → human acceptance → implication draft
                 → advisory MLflow judge → human approval → eligible teaching export
```

Teaching and industry share all processing, review, and retrieval code. `collection` separates them. Search tiers are `library`, `reviewed`, and `approved`; none is implicitly promoted to another.

## Storage

Seven research-owned Delta tables use the configured prefix: `sources`, `chunks`, `findings`, `recommendations`, `reviews`, `runs`, and `search_documents`. SQL eligibility views provide the current read model. Sources, passages, findings, implications and review events are append-only through this API; runs record started/completed/failed status. Search documents are a rebuildable derived table with Change Data Feed enabled.

The reference volume retains original bytes and per-run parser, preparation, extraction, retrieval, and assessment JSON. Research run records link to those artifact directories and, when configured, MLflow run/trace IDs. Parser output includes page geometry; search records keep physical PDF page numbers, which can differ from printed page labels.

Views exclude failed/incomplete runs, expired sources, withdrawn sources, rejected findings and unapproved implications. An implication is eligible only when every supporting finding is currently accepted. Reactivating a withdrawn source requires fresh acceptance of its findings, and changed finding review requires fresh implication approval.

Publication is one Delta MERGE into the derived search table followed by an explicit index-sync request. Serving revalidates every candidate against the current eligibility view, so stale index content cannot override a withdrawal. This is current-status checking, not a multi-table transactional guarantee against concurrent administrators; serialize operational mutations.

## Ownership and boundaries

- Reuse existing `workspace.magneto` catalog/schema and `references` volume. No grant or namespace provisioning.
- Research owns its tables, index, endpoint, manual jobs and separate MLflow experiment.
- Broad library search is an internal research interface, not the shared teaching retrieval contract.
- `export-guidance` projects reviewed internal evidence onto v1. It does not append internal fields or connect the live director.
- Databricks Catalog Explorer and the read-only operations notebook expose evidence and review queues. User review actions remain explicit authenticated CLI commands.
- Personal interaction analysis, learner-profile updates and physical execution are separate components.

## Managed capabilities and remaining logic

Databricks performs parsing, contextual search preparation, structured extraction, embeddings, indexing, SQL joins, run storage and MLflow judging. Local code validates provenance, computes immutable IDs, enforces publication eligibility, records decisions, and returns cited search results. It does not implement a graph database, vector engine or custom PDF parser.
