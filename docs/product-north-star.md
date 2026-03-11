# Product North Star

## Current Focus
Financenews is an **internal-operator-first financial intelligence platform**.

The product is optimized for operators who need to:

- keep ingestion trustworthy and current,
- understand source and connector health quickly,
- verify provenance and freshness before trusting downstream output,
- expose stable contracts for future UI and agent workflows.

## What Makes The Product Valuable

- **Reliable ingest over speculative AI**: fresh, attributable data is more valuable than a larger set of unstable AI features.
- **Operational clarity**: operators should be able to see when data is healthy, stale, degraded, or coming from fallback mode.
- **Stable contracts**: backend schemas and request/response envelopes should remain dependable so dashboards, automation, and future agents can build on them safely.
- **Incremental evolution**: we prefer compatibility-preserving refactors over clean-slate rewrites.

## Primary User
The primary user for the current phase is the **internal operator / maintainer**.

Secondary users:

- analyst-facing consumers of the dashboard,
- developers integrating against the API,
- future read-oriented research agents.

## Not The Current Priority

- autonomous agent execution,
- predictive trading or execution systems,
- speculative ML expansion without stronger data provenance,
- replacing the whole stack with a new framework.

## Near-Term Product Standard
Every major platform change should improve at least one of these:

- freshness visibility,
- source-of-truth clarity,
- API contract stability,
- operator control-plane reliability,
- evidence quality for future agent workflows.
