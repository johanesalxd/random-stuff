# Google Cloud Data Contracts — Executive Presentation Slides

This directory contains the executive presentation deck explaining the Google Cloud Data Contracts architecture, the 4 defense-in-depth gates, Open Data Contract Standard (ODCS v3.0), and Dataplex Auto Data Quality.

The presentation is built with [Marp](https://marp.app/) (Markdown presentation ecosystem). The architecture diagram in `assets/` is authored in Mermaid (`*.mmd`) and compiled to SVG (`*.svg`) for vector rendering.

```
slides/
├── data-contracts-presentation.md     # Marp presentation markdown source
├── data-contracts-presentation.html   # Pre-compiled standalone interactive HTML deck
├── data-contracts-presentation.pdf    # Pre-compiled high-resolution PDF presentation (10 slides)
├── assets/
│   ├── architecture.mmd               # Mermaid diagram source: 4-Defense-Gate Architecture
│   └── architecture.svg               # Rendered SVG vector diagram
└── README.md                          # Toolchain and presentation documentation
```

---

## Slide Deck Outline (10 Slides)

| Slide | Title | Core Message / Takeaway |
| :---: | :--- | :--- |
| **1** | **Title Slide** | *Enterprise Data Contracts on Google Cloud: Shift-Left Governance, Wire Ingress Gates & Dataplex Auto DQ* |
| **2** | **The Core Problem** | The "Dump-and-Pray" Pipeline Trap: Silent schema mutations, uncontained blast radius, and 10x-50x remediation costs. |
| **3** | **ODCS v3.0 Specification** | Single Source of Truth: How `contract.odcs.yaml` compiles to Pub/Sub Avro, BigQuery DDL, and Dataplex YAML specs. |
| **4** | **End-to-End Architecture** | Visual flowchart of the 4 Defense-in-Depth Gates: Producers → Wire Gate → Storage Ingestion → In-Database SLAs. |
| **5** | **Gates 1 & 2: Wire Defense** | Synchronous HTTP 400 `INVALID_ARGUMENT` rejection at Pub/Sub Schema Registry boundary (4 deterministic test vectors). |
| **6** | **Gate 3: Storage & DLQ** | BigQuery Storage Write API zero-ETL ingestion and automated Dead-Letter Queue (DLQ) quarantine on type mismatches. |
| **7** | **Gate 4: In-Database SLAs** | Dataplex Auto Data Quality serverless execution: Anti-wash trading (`buyer != seller`), 2-hour freshness, range checks. |
| **8** | **Executive Scorecard** | Real-time RAG (Red/Amber/Green) KPI dashboard, dimension breakdown, and point-and-click SQL forensics inspection queries. |
| **9** | **Turnkey Demonstration** | Dual market presets (`--preset=global` vs `--preset=sgx`) and 60-second offline simulation (`./run_demo.sh --simulated`). |
| **10**| **Summary & Key Takeaways**| Shift-left preventative ROI, native serverless architecture, and regulatory audit readiness (FINRA, SEC, MAS TRM). |

---

## How to Present

### Option A: Interactive HTML Presentation (Browser)
Open `data-contracts-presentation.html` in Chrome or any browser.
- Press **F** for Fullscreen mode.
- Use Left/Right Arrow keys to navigate slides.

### Option B: PDF Slide Deck
Open `data-contracts-presentation.pdf` in any PDF viewer or presentation software.

---

## Re-compiling the Presentation

If you modify `data-contracts-presentation.md` or the diagram in `assets/`:

### 1. Re-render Diagram (`.mmd` → `.svg`)
```bash
cat > /tmp/pptr.json << 'JSON'
{
  "executablePath": "/usr/bin/google-chrome",
  "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
}
JSON
npx -p @mermaid-js/mermaid-cli@10.9.1 mmdc -p /tmp/pptr.json -i assets/architecture.mmd -o assets/architecture.svg
```

### 2. Re-compile HTML & PDF
```bash
# Compile HTML
npx @marp-team/marp-cli data-contracts-presentation.md --html --allow-local-files -o data-contracts-presentation.html

# Compile PDF
PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome CHROME_PATH=/usr/bin/google-chrome \
  npx @marp-team/marp-cli data-contracts-presentation.md --pdf --allow-local-files -o data-contracts-presentation.pdf
```
