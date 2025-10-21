# Risk Management System Architecture Diagrams

This document contains the architectural diagrams for the Risk Management System, illustrating the onboarding process flow and the integration of internal and external services with the Risk Decision Engine.

---

## Diagram 1: Onboarding Process Flow

This diagram illustrates the end-to-end onboarding risk assessment process, showing how the Risk Decision Engine orchestrates various risk evaluation components and produces actionable outputs.

**Key Components:**
- **Process Flow**: The main data flow from onboarding checkpoint through the Risk API to the Decision Engine
- **Risk Evaluation Components**: Seven categories of risk checks performed by the engine
- **Outputs**: Three types of actions taken based on risk decisions

```mermaid
graph TD
    subgraph "Process Flow"
        ORC["Onboarding Risk Checkpoint"]
        RiskAPI["Risk API"]
        RDE["Risk Decision Engine"]
    end

    subgraph "Outputs"
        direction LR
        Admin["Admin Dashboard"]
        DB["Databases"]
        CM["Case Manager"]
    end

    subgraph "Risk Evaluation Components"
        direction TB
        Doc["Doc Verification<br/>(Fake/Synthetic, Duplicates)"]
        Screening["Screening<br/>(Sanctions, Blacklist, MC/Visa)"]
        Scoring["Risk Scoring<br/>(Fraud, Credit, AML)"]
        Web["Web Presence<br/>(Website, Reviews, Public DBs)"]
        Policy["Policy Checks<br/>(Channels, Limits, Reserves)"]
        Rules["Special Rules<br/>(Segment, Industry)"]
        ThirdParty["Third Party<br/>(Industry Check, Txn Laundering)"]
    end

    ORC -->|Data and artifacts| RiskAPI
    RiskAPI -->|Decisions| ORC
    RiskAPI <--> RDE

    RDE -.->|Actions| Admin
    RDE -.->|Updates| DB
    RDE -.->|Alerts| CM

    RDE --> Doc
    RDE --> Screening
    RDE --> Scoring
    RDE --> Web
    RDE --> Policy
    RDE --> Rules
    RDE --> ThirdParty

    style RDE fill:#4a4aff,stroke:#333,stroke-width:2px,color:#fff
    style Admin fill:#cfffe5,stroke:#333,stroke-width:1px
    style DB fill:#cfffe5,stroke:#333,stroke-width:1px
    style CM fill:#cfffe5,stroke:#333,stroke-width:1px
```

---

## Diagram 2: Risk Decision Engine Integration

This diagram shows the central role of the Risk Decision Engine in orchestrating a combination of internal microservices and external third-party products and services.

**Key Components:**
- **Internal Services**: Six internal microservices that feed data to the Decision Engine
- **Risk Decision Engine**: The core orchestration layer managing workflows, policies, and automation
- **External Products & Services**: Six third-party integrations for specialized risk assessments

**Integration Patterns:**
- Both internal and external services use bidirectional communication (↔) with the Decision Engine

```mermaid
graph LR
    subgraph "Internal Services"
        direction TB
        IS1["List Screening"]
        IS2["Rule Engine"]
        IS3["Limits"]
        IS4["Reserves"]
        IS5["Scoring"]
        IS6["Custom Fraud Engine"]
    end

    RDE["Risk Decision Engine<br/><br/>Workflows<br/>Policies<br/>Orchestration<br/>Automation"]

    subgraph "External Products & Services"
        direction TB
        ES1["Forter"]
        ES2["Name Screening"]
        ES3["Web Presence"]
        ES4["Doc Verification"]
        ES5["Txn Laundering"]
        ES6["Credit Checks"]
    end

    IS1 <--> RDE
    IS2 <--> RDE
    IS3 <--> RDE
    IS4 <--> RDE
    IS5 <--> RDE
    IS6 <--> RDE

    RDE <--> ES1
    RDE <--> ES2
    RDE <--> ES3
    RDE <--> ES4
    RDE <--> ES5
    RDE <--> ES6

    style RDE fill:#4a4aff,stroke:#333,stroke-width:2px,color:#fff
    style IS1 fill:#d6eaff,stroke:#333,stroke-width:1px
    style IS2 fill:#d6eaff,stroke:#333,stroke-width:1px
    style IS3 fill:#d6eaff,stroke:#333,stroke-width:1px
    style IS4 fill:#d6eaff,stroke:#333,stroke-width:1px
    style IS5 fill:#d6eaff,stroke:#333,stroke-width:1px
    style IS6 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES1 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES2 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES3 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES4 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES5 fill:#d6eaff,stroke:#333,stroke-width:1px
    style ES6 fill:#d6eaff,stroke:#333,stroke-width:1px
```

---

## Usage Notes

These diagrams are designed to be embedded in documentation, presentations, or architecture review materials. The Mermaid syntax ensures they can be rendered in:

- GitHub/GitLab markdown files
- Confluence pages (with Mermaid plugin)
- Documentation sites (MkDocs, Docusaurus, etc.)
- Presentation tools that support Mermaid

**Color Scheme:**
- **Blue (#4a4aff)**: Risk Decision Engine (core component)
- **Light Blue (#d6eaff)**: Internal and external services
- **Light Green (#cfffe5)**: Output systems
