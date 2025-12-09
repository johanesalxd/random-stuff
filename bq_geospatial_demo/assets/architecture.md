# Hybrid Logistics Architecture

This document provides visual diagrams of the route optimization architecture.

## System Architecture

```mermaid
graph TB
    subgraph "Data Layer"
        A[NYC Citibike Dataset<br/>2,251 Active Stations]
    end

    subgraph "Strategic Planning - BigQuery"
        B[Territory Assignment<br/>Geohash Clustering]
        C[Route Sequencing<br/>Spatial Indexing]
        D[Distance Calculation<br/>ST_MAKELINE]
    end

    subgraph "Tactical Execution - Google Maps"
        E[Cloud Function<br/>Python Bridge]
        F[Google Maps API<br/>Directions + TSP Solver]
        G[Road Network Polyline<br/>Traffic-Aware Routes]
    end

    subgraph "Visualization"
        H[BigQuery Geo Viz<br/>Interactive Map]
        I[Looker Studio<br/>Dashboards]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    D --> H
    H --> I

    style A fill:#e1f5ff
    style B fill:#fff9c4
    style C fill:#fff9c4
    style D fill:#fff9c4
    style E fill:#c8e6c9
    style F fill:#c8e6c9
    style G fill:#c8e6c9
    style H fill:#f3e5f5
    style I fill:#f3e5f5
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant BigQuery
    participant CloudFunction
    participant MapsAPI
    participant GeoViz

    User->>BigQuery: Run SQL Query
    BigQuery->>BigQuery: Cluster 500 stops into 10 zones
    BigQuery->>BigQuery: Sequence stops using geohash
    BigQuery->>BigQuery: Generate straight-line routes
    BigQuery->>CloudFunction: Send Zone 1 waypoints
    CloudFunction->>MapsAPI: Request optimized route
    MapsAPI->>MapsAPI: Solve TSP + apply traffic
    MapsAPI->>CloudFunction: Return polyline + metrics
    CloudFunction->>BigQuery: Return JSON response
    BigQuery->>BigQuery: Decode polyline to GEOGRAPHY
    BigQuery->>GeoViz: Return visualization data
    GeoViz->>User: Display interactive map
```

## Component Breakdown

```mermaid
graph LR
    subgraph "Act 1: Strategic Planning"
        A1[Raw Data<br/>500 Stations]
        A2[Geohash Clustering<br/>NTILE Function]
        A3[10 Balanced Zones]
        A1 --> A2 --> A3
    end

    subgraph "Act 2: Tactical Sequencing"
        B1[Clustered Stations]
        B2[Spatial Indexing<br/>ST_GEOHASH]
        B3[Ordered Routes<br/>ST_MAKELINE]
        B1 --> B2 --> B3
    end

    subgraph "Act 3: Operational Execution"
        C1[Sequenced Waypoints]
        C2[Remote Function Call]
        C3[Maps API Response]
        C4[Road Network Path]
        C1 --> C2 --> C3 --> C4
    end

    A3 --> B1
    B3 --> C1

    style A1 fill:#e1f5ff
    style A2 fill:#fff9c4
    style A3 fill:#fff9c4
    style B1 fill:#fff9c4
    style B2 fill:#f0f4c3
    style B3 fill:#f0f4c3
    style C1 fill:#c8e6c9
    style C2 fill:#c8e6c9
    style C3 fill:#c8e6c9
    style C4 fill:#c8e6c9
```

## Technology Stack

```mermaid
graph TD
    subgraph "BigQuery Capabilities"
        BQ1[Geospatial Functions<br/>ST_GEOGPOINT, ST_GEOHASH, ST_MAKELINE]
        BQ2[Window Functions<br/>NTILE, ROW_NUMBER]
        BQ3[Aggregations<br/>ARRAY_AGG, ST_CENTROID_AGG]
        BQ4[Remote Functions<br/>Call external APIs]
    end

    subgraph "Google Maps Platform"
        GM1[Directions API<br/>Route calculation]
        GM2[Waypoint Optimization<br/>TSP solver]
        GM3[Traffic Data<br/>Real-time conditions]
        GM4[Encoded Polylines<br/>Efficient geometry]
    end

    subgraph "Cloud Infrastructure"
        CF1[Cloud Functions Gen2<br/>Python 3.11]
        CF2[BigQuery Connections<br/>Service account auth]
        CF3[Secret Manager<br/>API key storage]
    end

    BQ4 --> CF1
    CF1 --> GM1
    GM1 --> GM2
    GM2 --> GM3
    GM3 --> GM4

    style BQ1 fill:#fff9c4
    style BQ2 fill:#fff9c4
    style BQ3 fill:#fff9c4
    style BQ4 fill:#fff9c4
    style GM1 fill:#c8e6c9
    style GM2 fill:#c8e6c9
    style GM3 fill:#c8e6c9
    style GM4 fill:#c8e6c9
    style CF1 fill:#e1f5ff
    style CF2 fill:#e1f5ff
    style CF3 fill:#e1f5ff
```

## Cost Optimization Strategy

```mermaid
graph LR
    A[10,000 Raw Orders] --> B{BigQuery Clustering}
    B --> C[10 Territories<br/>~1,000 stops each]
    C --> D{BigQuery Sequencing}
    D --> E[10 Optimized Routes<br/>~100 stops each]
    E --> F{Cost Decision}
    F -->|Strategic View| G[Use BigQuery Routes<br/>Cost: $0.01]
    F -->|Tactical View| H[Send to Maps API<br/>Cost: $0.05]

    style A fill:#ffcdd2
    style B fill:#fff9c4
    style C fill:#fff9c4
    style D fill:#f0f4c3
    style E fill:#f0f4c3
    style F fill:#e1f5ff
    style G fill:#c8e6c9
    style H fill:#c8e6c9
```

## Key Metrics

| Metric | BigQuery (Strategic) | Google Maps (Tactical) |
|--------|---------------------|------------------------|
| **Processing Time** | < 1 second | 2-5 seconds per route |
| **Cost per Query** | $0.000005 | $0.005 per route |
| **Scalability** | Millions of points | < 25 waypoints per request |
| **Accuracy** | Geodesic distance | Road network distance |
| **Traffic Awareness** | No | Yes (real-time) |
| **Use Case** | Planning, budgeting | Driver navigation |

## Demo Scenarios

1. **Scenario 1: Fleet Planning** - Assign 500 stops to 10 trucks (BigQuery only)
2. **Scenario 2: Route Sequencing** - Order stops within territories (BigQuery only)
3. **Scenario 3: TSP Solver** - Nearest neighbor algorithm (BigQuery scripting)
4. **Scenario 4: Combined View** - All layers in one visualization (BigQuery only)
5. **Scenario 5: Hybrid Execution** - Strategic + Tactical (BigQuery + Maps API)
