# Historical Parity Ledger

Baseline: repository tree at commit `6a6cefeeccb38ec6378204ead31dee76168503fa`.

Merged-main anchor: `origin/main` at
`af410541704830c258c79aaa8c7dfaec479b41db`, reviewed on 2026-07-16 after
PR #19 merged. Its cookbook tree matches the reviewed PR commit `975e650`.

This ledger records disposition, not current product authority. Retrieve the
first-party URLs in `REFERENCES.md` and each query section before relying on a
product claim.

## Current-main integration disposition

| Current-main surface | Disposition in this hardening pass |
|---|---|
| 25 query IDs and six analytical report mappings | Preserved one-for-one |
| Seven ordered reports and 14 synthetic fixtures | Preserved and reconciled |
| Single-project workload analysis | Made explicit; parallel project runs remain independent |
| Historical Hybrid recommendation | Retained as a documented strategy family but always `INELIGIBLE`; the single-project corpus cannot support cross-project evidence |
| Project-and-region-only inputs | Replaced with explicit workload, query, and administration projects, a parameterized window, and conditional dataset/economic inputs |
| Optional current-configuration report | Replaced with an always-produced evidence report, including a valid observed absence of reservations or commitments |
| Fixed 30-day workload SQL | Replaced with one inclusive/exclusive window, defaulting to 30 complete UTC days |
| Timeline job-creation boundary | Replaced with a derived overlap bound so observable jobs created before the window retain their in-window timeslices |
| Optional-query applicability | Split into a business trigger and execution prerequisites with deterministic terminal status |
| Generic recommendations and Slot Recommender | Separated into Query 4.11 status and an independent report substatus |
| Unsalted diagnostic hashes | Replaced with per-run salted fingerprints; normalized query hashes remain separately labelled |
| Storage billing "savings" output | Replaced with neutral forecast sensitivity pending Billing and storage-semantics reconciliation |
| BigQuery MCP, mutation commands, fixed prices, CI, and validators | Remain absent |

| Historical surface | Current surface | Status | Reason |
|---|---|---|---|
| Query 0.1 reservations | Query 0.1 | Preserved and corrected | Adds edition, autoscaling, predictability, idle-sharing, and configured-limit semantics. |
| Query 0.2 assignments | Query 0.2 | Preserved and scoped | Keeps administration project and location explicit. |
| Query 0.2a commitment reconstruction | Query 0.2a | Safely replaced | Returns current inventory and raw limited-retention events; never sums change events into false history. |
| Query 0.3 utilization | Query 0.3 | Safely replaced | Uses time-aligned capacity and labels one workload project's contribution instead of reservation-wide utilization. |
| Query 0.4 idle slots | Query 0.4 | Safely replaced | Reports baseline-minus-project-use only; never calls it reservation headroom, waste, or idle capacity. |
| Query 0.5 billing classification | Query 0.5 | Safely replaced | Separates cached, positive-slot, failed, and zero/unknown-compute jobs. |
| Query 1.1 percentiles | Query 1.1 | Preserved and corrected | Includes zero-use hours and complete-hour bounds. |
| Query 1.2 project ranking | Query 1.2 | Safely replaced | A project-scoped view reports one project and cannot rank projects. |
| Query 1.3 patterns | Query 1.3 | Preserved and privacy-hardened | Pseudonymizes principals and does not infer cross-project Hybrid eligibility. |
| Query 4.1 contention | Query 4.1 | Preserved with fallback | Adds a documented runnable-units pressure proxy when insight fields are unavailable. |
| Query 4.2 expensive queries | Query 4.2 | Safely replaced | Adds processed/billed-byte gaps and privacy-safe workload/table fingerprints; emits no dollars. |
| Query 4.3 slow queries | Query 4.3 | Preserved and privacy-hardened | Uses fingerprints and correct GiB units. |
| Query 4.4 reservation simulation | Query 4.4 | Safely replaced | Labels output historical demand sensitivity, not queueing, runtime, billing, or reservation simulation. |
| Query 4.5 weekly trend | Query 4.5 | Preserved | Retains slot-hour trend evidence. |
| Query 4.8 raw errors | Query 4.8 | Safely replaced | Keeps taxonomy, positive-compute failure counts/slot-hours, and hashed handles; raw messages require private ephemeral inspection. |
| Query 4.9 average slots | Query 4.9 | Preserved and relabelled | Treats successful, non-cached, positive-compute per-job averages as a distribution, not concurrent capacity. |
| Query 4.10 queue pressure | Query 4.10 | Safely replaced | Counts distinct queued interactive jobs per second before comparison with the project/region limit. |
| Query 4.11 recommendations | Query 4.11 | Safely replaced | Separates generic recommendations from supported Slot Recommender evidence. |
| Query 4.12 performance insights | Query 4.12 | Preserved with first-party authority | Retains BigQuery Utils lineage while grounding schema in official JOBS documentation. |
| Query 4.13 BI Engine diagnostics | Query 4.13 | Preserved with first-party authority | Retains lineage and labels repeated slot-hours non-additive. |
| Query 4.14 partition/cluster audit | Query 4.14 | Preserved and corrected | Uses dataset-scoped COLUMNS and non-additive reference signals. |
| Query 5.1 streaming | Query 5.1 | Preserved and conditional | Uses Storage Write API evidence and does not infer legacy streaming. |
| Query 6.1 storage | Query 6.1 | Safely replaced | Keeps logical and physical storage separate. |
| Query 6.2 old tables | Query 6.2 | Safely replaced | Age is triage, never proof of disuse or permission to delete. |
| Query 6.3 storage-model DDL | Query 6.3 | Safely replaced | Read-only sensitivity with dated user inputs; no DDL or fixed prices. |
| BigQuery MCP live execution | `bq`/`gcloud` read-only data access | Intentionally retired | Keeps documentation retrieval separate from live project access. |
| Fixed price and savings constants | Runtime documentation/pricing evidence | Intentionally retired | Prices vary by date, location, currency, SKU, and contract. |
| Runnable mutation commands and generated DDL | Prose recommendations with official links | Intentionally retired | The user constructs current mutation syntax outside this read-only skill. |
| Raw principals, job IDs, query text, and error messages | Fingerprints and private ephemeral follow-up | Intentionally retired | Reduces disclosure while preserving diagnostic grouping. |
| Daily slot-utilization monitor | Queries 1.1, 1.3, and 4.5 | Intentionally retired | The historical average excluded zero periods and was not a defensible reservation-utilization metric. |
| Reservation monitor | Query 0.3 project contribution | Safely folded in | Preserves job count and slot-hours with explicit workload-project scope. |
| Seven reports and sample fixtures | Seven reports and 14 synthetic samples | Preserved and enhanced | Adds ordered headings, evidence labels, documentation checks, and explicit gaps. |
