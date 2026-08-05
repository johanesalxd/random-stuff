# Semantic Analytics ADK Flow

Gemini did not fail to choose the semantic workflow or domain during the
baseline evaluation. It consistently selected the relevant `thelook_orders` or
`thelook_inventory` context.

The semantic-selection score was lower because the metric requires the exact
minimal concept IDs defined by the oracle. Eight selections produced correct
SQL and exact results but contained redundant or equivalent semantic choices.

## Runtime Flow

```mermaid
flowchart TD
    START([User question]) --> REG[Load semantic contracts]
    REG --> SELECTOR["Gemini selector<br/>Choose context, metric, dimension, and relationship IDs"]
    SELECTOR --> RESOLVE{Resolve selection}

    RESOLVE -->|Valid narrow selection| NARROW[Load narrow catalog context]
    RESOLVE -->|"No match, invalid, ambiguous,<br/>or broad requested"| BROAD[Load broad catalog context]

    NARROW --> CHECK{Narrow context sufficient?}
    CHECK -->|Yes| PREP[Prepare grounded SQL context]
    CHECK -->|No| BROAD

    BROAD --> BCHECK{Broad context grounded?}
    BCHECK -->|Yes| PREP
    BCHECK -->|No| CLARIFY[Return clarification request]

    PREP --> SQLGEN["Claude SQL generator<br/>Generate one BigQuery SELECT"]
    SQLGEN --> EXEC{Execute SQL once}

    EXEC -->|Success| RESULT[Prepare result rows]
    EXEC -->|Query error| SQLERROR[Return query error]

    RESULT --> SUMMARY["Gemini summarizer<br/>Explain the result"]
    SUMMARY --> ANSWER([Final answer])

    SELECTOR -.->|Model or provider exception| ABORT[Invocation aborts]
    SQLGEN -.->|Model or provider exception| ABORT
    SUMMARY -.->|Model or provider exception| ABORT

    style ANSWER fill:#d5e8d4,stroke:#82b366
    style CLARIFY fill:#fff2cc,stroke:#d6b656
    style SQLERROR fill:#f8cecc,stroke:#b85450
    style ABORT fill:#f8cecc,stroke:#b85450
```

## Normal Success Path

```mermaid
flowchart LR
    Q[Question] --> S["Gemini selects<br/>thelook_orders"]
    S --> G[Ground against contract and catalog]
    G --> C["Claude generates<br/>bounded SQL"]
    C --> BQ[(BigQuery)]
    BQ --> R[Result rows]
    R --> SUM[Gemini summarizes]
    SUM --> A[Final answer]

    style A fill:#d5e8d4,stroke:#82b366
```

For example:

```text
Question:
How many completed orders were placed?

Gemini selection:
context       = thelook_orders
metric        = completed_order_count
dimensions    = []
relationships = []

Claude SQL intent:
COUNT(DISTINCT order_id)
WHERE status = 'Complete'

Result:
31,132
```

This case passed semantic selection and exact BigQuery result matching.

## Recovery And Failure Paths

The workflow has three business-level exits and one unhandled operational exit:

- A successful query is summarized and returned as the final answer.
- Insufficient narrow context triggers broad catalog grounding.
- Broad context that is still insufficient returns a clarification request.
- A BigQuery error returns a query-error response.
- A model or provider exception aborts the invocation before a routed response.

The initial Sonnet 5 smoke attempt followed the operational failure path. SQL
generation aborted with `404 NOT_FOUND` because `claude-sonnet-5` was not enabled
for the project. Sonnet 4.5 was enabled and completed the workflow successfully.

## Evaluation Flow

The ADK evaluation applies two independent metrics to each invocation.

```mermaid
flowchart TD
    RUN[ADK workflow execution] --> EVENTS[Collect ADK invocation events]

    EVENTS --> SEM["Compare Gemini selector JSON<br/>with exact oracle IDs"]
    EVENTS --> SQL[Extract generated SQL]

    SQL --> DRY[BigQuery dry run]
    DRY --> SAFE{"SELECT, expected sources,<br/>and under 1 GB?"}
    SAFE -->|No| RESULTFAIL[BigQuery metric fails]
    SAFE -->|Yes| BOTH["Execute candidate SQL<br/>and gold SQL"]
    BOTH --> COMPARE{Exact results match?}
    COMPARE -->|No| RESULTFAIL
    COMPARE -->|Yes| RESULTPASS[BigQuery metric passes]

    SEM --> EXACT{Exact semantic IDs?}
    EXACT -->|Yes| SEMPASS[Semantic metric passes]
    EXACT -->|"Equivalent, redundant,<br/>or incorrect IDs"| SEMFAIL[Semantic metric fails]

    SEMPASS --> CASE{Both metrics pass?}
    SEMFAIL --> CASE
    RESULTPASS --> CASE
    RESULTFAIL --> CASE

    CASE -->|Yes| PASS[Case passes]
    CASE -->|No| FAIL[Case fails strict evaluation]

    style PASS fill:#d5e8d4,stroke:#82b366
    style FAIL fill:#f8cecc,stroke:#b85450
    style RESULTPASS fill:#d5e8d4,stroke:#82b366
    style SEMFAIL fill:#fff2cc,stroke:#d6b656
```

## Selection Failure: Redundant Relationship

For completed orders by country, the oracle expected:

```json
{
  "context_id": "thelook_orders",
  "metric_ids": ["completed_order_count"],
  "dimension_ids": ["country"],
  "relationship_ids": []
}
```

Gemini sometimes selected:

```json
{
  "context_id": "thelook_orders",
  "metric_ids": ["completed_order_count"],
  "dimension_ids": ["country"],
  "relationship_ids": ["users__orders"]
}
```

The relationship is correct but unnecessary because the semantic resolver
automatically computes and injects the required join.

```mermaid
flowchart LR
    ORACLE["Oracle:<br/>metric and country"] --> AUTO["Resolver automatically<br/>injects users__orders"]
    GEMINI["Gemini:<br/>metric, country, and users__orders"] --> SAME[Same grounded context]
    AUTO --> SAME
    SAME --> SQL[Same correct SQL result]

    GEMINI -.-> STRICT["Strict metric fails:<br/>extra relationship ID"]

    style SAME fill:#d5e8d4,stroke:#82b366
    style STRICT fill:#fff2cc,stroke:#d6b656
```

This is an over-selection problem, not a wrong-path problem.

## Selection Failure: Equivalent Metric

For top users by completed revenue, the oracle expected:

```text
top_users_by_completed_revenue + user_id
```

Gemini consistently selected:

```text
completed_revenue + user_id
```

Both choices generated the same grouped, ordered, and limited result.

```mermaid
flowchart TD
    Q[Top 10 users by completed revenue] --> CHOICE{Gemini metric choice}

    CHOICE -->|Oracle choice| SPECIAL["top_users_by_completed_revenue<br/>and user_id"]
    CHOICE -->|Observed choice| GENERIC["completed_revenue<br/>and user_id"]

    SPECIAL --> SQL1["Group by user<br/>order descending<br/>limit 10"]
    GENERIC --> SQL2["Group by user<br/>order descending<br/>limit 10"]

    SQL1 --> GOLD[Exact gold result]
    SQL2 --> GOLD

    GENERIC -.-> STRICT[Strict semantic metric fails]

    style GOLD fill:#d5e8d4,stroke:#82b366
    style STRICT fill:#fff2cc,stroke:#d6b656
```

This exposes overlap in the semantic contract. The generic and specialized
metrics can answer the same question, but the exact oracle accepts only the
specialized metric ID.

## Baseline Interpretation

| Measurement | Result |
|---|---:|
| Semantic workflow and domain selection | Working |
| Catalog grounding | Working |
| Exact BigQuery result accuracy | 36/36, 100% |
| Strict minimal semantic selection | 28/36, 77.8% |

The issue is selector consistency and contract ambiguity, not downstream SQL
correctness. None of the eight strict semantic-selection mismatches produced an
incorrect BigQuery result.
