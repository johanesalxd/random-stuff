``` mermaid
graph TB
    %% Core Analogy Section
    subgraph Core["<b>Core Analogy</b>"]
        direction LR
        K_Cluster["<b>Kubernetes Cluster</b><br/>Collection of nodes"]
        BQ_Reservation["<b>BigQuery Reservation</b><br/>Pool of slots"]
        K_Cluster -.->|"≈"| BQ_Reservation

        K_Nodes["<b>Kubernetes Nodes</b><br/>Individual machines"]
        BQ_Slots["<b>BigQuery Slots</b><br/>Individual compute units"]
        K_Nodes -.->|"≈"| BQ_Slots
    end

    %% Strategy Implementations
    subgraph Strategies["<b>Two Management Strategies</b>"]
        direction TB

        subgraph S1["<b>Strategy 1: Single Pool</b>"]
            direction TB
            S1_Title["<b>All-in-One Approach</b>"]
            S1_K8s["🔷 One Giant Cluster"]
            S1_BQ["🔶 One Reservation"]
            S1_Benefits["✅ Max Efficiency<br/>✅ Simple Management"]

            S1_Title --> S1_K8s
            S1_Title --> S1_BQ
            S1_K8s --> S1_Benefits
            S1_BQ --> S1_Benefits
        end

        subgraph S2["<b>Strategy 2: Multiple Pools</b>"]
            direction TB
            S2_Title["<b>Isolate & Share Approach</b>"]
            S2_K8s["🔷 Multiple Sub-Clusters"]
            S2_BQ["🔶 Multiple Reservations"]
            S2_Benefits["✅ Better Isolation<br/>✅ Fault Tolerance<br/>✅ Team Separation"]
            S2_Sharing["💡 Idle Slot Sharing"]

            S2_Title --> S2_K8s
            S2_Title --> S2_BQ
            S2_K8s --> S2_Benefits
            S2_BQ --> S2_Benefits
            S2_BQ --> S2_Sharing
        end
    end

    %% Clean connections from core concepts to strategies
    K_Cluster --> S1_Title
    K_Cluster --> S2_Title
    BQ_Reservation --> S1_Title
    BQ_Reservation --> S2_Title

    %% Styling
    classDef kubernetes fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e40af
    classDef bigquery fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#92400e
    classDef strategy fill:#f9fafb,stroke:#6b7280,stroke-width:2px
    classDef benefit fill:#dcfce7,stroke:#22c55e,stroke-width:1px,color:#166534
    classDef title fill:#fdf4ff,stroke:#a855f7,stroke-width:2px
    classDef core fill:#f8fafc,stroke:#64748b,stroke-width:1px

    class K_Cluster,K_Nodes,S1_K8s,S2_K8s kubernetes
    class BQ_Reservation,BQ_Slots,S1_BQ,S2_BQ bigquery
    class S1,S2,Strategies strategy
    class S1_Benefits,S2_Benefits,S2_Sharing benefit
    class S1_Title,S2_Title title
    class Core core
```