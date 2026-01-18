# Optimization Opportunities (30-Day Analysis)

## 1. Slot Contention
*   **Findings**: No slot contention events were detected.
*   **Impact**: Jobs are not waiting for resources.

## 2. Expensive Queries (>1 TB)
*   **Findings**: No queries exceeded the 1 TB threshold.
*   **Recommendation**: Cost control mechanisms are currently sufficient for the query volume.

## 3. Slow Queries
*   **Findings**: The longest running query took only 3 seconds.
*   **Performance**: Query performance is excellent, likely due to small data volumes or simple query complexity.

## 4. Reservation Simulation
| Reservation Size | Hours Within | Hours Exceeding | Utilization % |
|:--- |:--- |:--- |:--- |
| **50 Slots** | 105 | 0 | 0.0% |
| **100 Slots** | 105 | 0 | 0.0% |
| **500 Slots** | 105 | 0 | 0.0% |
*   **Conclusion**: Any reservation would be >99% wasted.

## 5. Error Analysis
| Error Reason | Count | % of Errors | Description |
|:--- |:--- |:--- |:--- |
| **accessDenied** | 27 | 100% | User does not have masked access or raw data access to protected columns. |

*   **Critical Issue**: High number of `accessDenied` errors related to column-level security on `demo_dataset.employees` (columns: `salary`, `ssn`, `email`, `bank_account`).
*   **Action**: Review Data Catalog Policy Tags and IAM permissions for users querying `demo_dataset.employees`.

## 6. Job Impact Analysis (Commitment Levels)
| Scenario | Commitment | Jobs Exceeding | % Jobs Exceeding |
|:--- |:--- |:--- |:--- |
| **P50 Commitment** | 0.1 Slots | 113 | 28.3% |
| **Average Commitment** | 5.2 Slots | 54 | 13.5% |
| **P90 Commitment** | 15.0 Slots | 24 | 6.0% |
| **P95 Commitment** | 31.3 Slots | 12 | 3.0% |

*   **Note**: "Average Commitment" calculation (5.2 slots) seems skewed by short duration jobs in the micro-accounting. Given the P95 usage is actually 0.0 in the timeline view, these job-level stats likely reflect instantaneous bursts of very short duration.
