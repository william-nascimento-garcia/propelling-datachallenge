# Design Decisions: Demo Talking Points

These are short answers to the five design questions in the challenge brief.

## 1. Why Medallion? What does each layer give you that a single layer would not?

A single layer mixes three different responsibilities: **keeping the source**, **defining the truth** and **serving a use case**. When these are mixed:

- every fix means re-reading the source;
- business rules get copied into every report, so two dashboards show two different "revenues";
- any change to the source schema breaks consumers directly.

Medallion separates these responsibilities, and each layer gets its own contract:

| Layer | Contract | Who depends on it |
|---|---|---|
| Bronze | "This is exactly what the source said, and when." | Data engineers (reprocessing, audit) |
| Silver | "This is the cleaned, agreed meaning of the data." | Every analytical use case |
| Gold | "This is the shape this consumer needs, and it won't break." | BI tools, analysts, business users |

There is also an operational benefit: problems are isolated. A source change breaks Bronze → Silver, not the dashboard. A new use case adds a Gold mart without touching Silver.

## 2. Criteria for Bronze vs Silver vs Gold

I ask three questions of every transformation, in order:

1. **Does it change the meaning or content of the source?** If not (only lineage metadata), it goes in **Bronze**.
2. **Is it true regardless of who consumes the data?** Deduplication, renaming, typing (keys as strings, numbers with explicit precision), decoding codes, splitting packed attributes, conforming geography and the definition of net revenue all go in **Silver**.
3. **Does it exist because of a specific consumer or question?** Grain choice, denormalisation into a star, surrogate keys for BI, aggregations, KPI rates and PII exclusion all go in **Gold**.

Example: `net_amount = extended_price × (1 − discount)` is in Silver because it is the company's definition of revenue. `gross_margin_pct` per month × region is in Gold because it exists for the commercial dashboard.

## 3. Why this use case? Who consumes it, and what decisions does it support?

- **Why:** the TPC-H data contains price, discount and supply cost per part and supplier. That is enough to calculate **real gross margin**, the metric a wholesaler's commercial team cares about most. The dataset also has committed vs actual delivery dates and return flags, so supplier performance comes from the same fact table at almost no extra cost.
- **Consumers:**
  - Commercial Director and Sales / Category Managers: revenue, discount and margin by region, segment, brand and time.
  - Supply Chain / Procurement Manager: late delivery rate, delays, returns and revenue at risk per supplier.
- **Decisions supported:**
  - Discount policy: which segments are over-discounted.
  - Commercial focus: which regions and brands to grow.
  - Supplier management: which suppliers to renegotiate, replace or reward.

## 4. What would I add for production?

- **Ingestion and history:** incremental, append-only Bronze with history, Snowpipe or Openflow for real sources, `source freshness` with SLAs, and snapshots (SCD2) on customer and supplier.
- **Performance:** incremental `merge` on the fact, clustering reviewed against real query patterns, and separate warehouse sizes per workload.
- **Testing strategy as a pyramid:**
  - source tests: completeness and keys;
  - Silver tests: keys not null and unique (proving deduplication), plus business rules;
  - in production I would add value-domain tests (accepted values, ranges) and referential integrity (relationships);
  - Gold: contracts plus reconciliation (`sum_matches`);
  - unit tests (`dbt unit tests`) for complex logic;
  - severity levels (warn vs error) per test.
- **Orchestration:** Airflow, Dagster or dbt Cloud, with retries, SLAs, and runs triggered when sources land rather than on a fixed cron.
- **Observability:**
  - Elementary for anomaly detection on volume, freshness and schema;
  - run artifacts stored in Snowflake (**already implemented**: an `on-run-end` hook writes every run's results to `AUDIT.DBT_RUN_RESULTS`);
  - Slack or Teams alerts;
  - cost monitoring via `ACCOUNT_USAGE` and resource monitors.
- **Security and governance:**
  - masking policies on PII and row access policies;
  - separate dev and prod databases (or accounts);
  - SSO for people and key-pair auth for services;
  - data contracts with source owners and model versioning.
- **Semantic layer:** metrics defined once (MetricFlow), so Power BI, Tableau and notebooks all show the same number.

## 5. CI/CD approach and its value

- **Branching:** feature branch → PR → `main`. `main` is production.
- **CI on every PR:**
  - lint (sqlfluff);
  - **Slim CI**: only modified models and their descendants are built and tested, in an isolated `CI_PR_<n>_*` schema;
  - unchanged upstream models are read from production with `--defer`;
  - the PR schemas are dropped afterwards.
- **CD on merge:** full `dbt build` in prod, docs regenerated and published to GitHub Pages, and the production `manifest.json` stored for the next state comparison.
- **Secrets:** a key-pair service user. The private key exists only in GitHub Secrets and on my machine, outside the repo.

**Value:** CI/CD treats data like software.

- No untested change reaches the dashboards.
- Reviewers see what changed and its downstream impact.
- CI cost stays low because only what changed is rebuilt.
- Deployments are repeatable and reversible (`git revert`).
- Documentation and lineage are never stale.
