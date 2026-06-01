# AuditChain 🔍

### A multi-agent AI system that audits SEC filings the way a senior auditor would — except it does it in 2 minutes for under $0.20.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-v0.110-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🌐 Live App
The production version of AuditChain is live at:
**[https://audit.lbai.dev](https://audit.lbai.dev)**

> [!IMPORTANT]
> **Want to test the platform?**  
> Access is currently restricted for security and cost management. If you are a recruiter, developer, or finance professional and would like a demo account, please **contact me directly** (links below).

---

## 🚩 The Problem
Forensic analysis of SEC 10-K filings is a nightmare of complexity. You have to verify accounting equations across years, calculate quantitative models like Beneish M-Score and Altman Z-Score, and perform qualitative language analysis across thousands of pages of legalese.

Big Four firms take days to do this and charge a fortune. Even then, massive frauds like Wirecard, Luckin Coffee, and Wells Fargo escaped detection for years. Human auditors get tired, they miss patterns, and they are expensive. In short: forensic auditing is slow, pricey, and surprisingly fallible.

## 🧠 The Approach
AuditChain explores a simple hypothesis: what if we could build a multi-agent system where each agent is a specialist in one dimension of the audit?

Coordinated by **LangGraph**, five specialized agents work together in a structured workflow. They don't just "chat" — they use validated tools to extract data, perform math, and search through text via **RAG (pgvector)**. Every decision is grounded in real filing data, and every agent output is validated against strict Pydantic schemas.

Before any agent sees the data, a **DQC-inspired ingestion validator** runs 5 layers of quality checks on the raw XBRL facts from SEC EDGAR — catching bad values, wrong periods, and cross-statement inconsistencies before they reach the models. It's an automated, high-fidelity forensic pipeline that keeps a full audit trail of its reasoning.

## ✨ What It Does
- **Multi-agent fraud detection pipeline**: 5 specialized agents coordinated via LangGraph.
- **DQC-inspired data quality validation**: 5-layer XBRL quality checks on ingestion — sign checks, period duration, cross-concept consistency, YoY plausibility, and cross-statement reconciliation.
- **Quarterly aggregation**: When a company's XBRL doesn't include an annual total (DQC Rule 0146 violation), the system reconstructs it by summing Q1+Q2+Q3+Q4 automatically.
- **Real-time progress streaming**: Watch agents work via Server-Sent Events (SSE) — both during ingestion and audit.
- **RAG over filing text**: High-density vector search using `pgvector` and `text-embedding-3-small`.
- **Quantitative forensic models**: Automated Beneish M-Score, Altman Z-Score, and Accruals analysis — with sector-aware gating via SIC codes (e.g. financial sector is excluded from Altman, which was calibrated for manufacturing).
- **Self-service company onboarding**: Ingest any of the ~10,000 SEC-registered companies on demand via a 5-stage pipeline (validate → download facts → download filings → parse XBRL → embed text).
- **Model-aware cost tracking**: Every audit's cost is calculated per message from the actual model name returned by the OpenAI API — pricing automatically reflects which agent uses which model.
- **JWT authentication**: Full user management with access/refresh tokens, rate limiting, and admin endpoints.
- **Persistent audit history**: Every run is stored in a relational database for future review.
- **Professional executive reports**: High-fidelity summaries with deterministic risk scoring (no LLM-guessed numbers).

## 🖼️ Demo
To see AuditChain in action, we've broken down the pipeline into three key stages:

### 1. Ingestion & Data Collection
![Data Collection](docs/screenshots/auditChain1.gif)
*The system fetches and indexes SEC filings, preparing the data for multi-agent analysis.*

### 2. Forensic Analysis (Reconciler & Quant)
![Forensic Analysis](docs/screenshots/auditChain2.gif)
*Agents verify accounting equations and apply forensic models (Beneish/Altman) to detect anomalies.*

### 3. Deep Investigation & Final Report
![Final Report](docs/screenshots/auditChain3.gif)
*The Investigator performs RAG-based analysis on qualitative disclosures, and the Supervisor generates the final executive report.*

## 🏗️ Architecture
```mermaid
graph TD
    User((User/Browser)) -->|Next.js 15| FE[Frontend App]
    FE -->|REST / SSE| API[FastAPI Backend]
    API -->|JWT Auth| Auth[Auth Service]

    subgraph "Ingestion Pipeline"
        API --> ING[5-Stage Ingestion]
        ING -->|validate / download / parse / embed| SEC[SEC EDGAR API]
        ING -->|DQC Quality Validator| DQC[5-Layer XBRL Checks]
        DQC --> DB[(PostgreSQL)]
    end

    subgraph "AI Audit Engine (LangGraph)"
        API --> LG[Workflow Controller]
        LG --> Collector[Collector Agent]
        LG --> Reconciler[Reconciler Agent]
        LG --> Quant[Quant Analyst Agent]
        LG --> Investigator[Investigator Agent]
        LG --> Supervisor[Supervisor Agent]
    end

    Investigator -->|Vector Search| PGV[(PostgreSQL + pgvector)]
    LG -->|LLM Calls| OAI[OpenAI GPT-4o / mini]
    LG -->|Persistence| DB

    style LG fill:#f9f,stroke:#333,stroke-width:2px
    style DQC fill:#ffe,stroke:#333,stroke-width:2px
```

The system uses a stateful graph where agents append their findings to a shared `AuditState`. The **Supervisor** acts as the final judge, consolidating reports and calculating the risk score. For a deeper dive into the "why" behind the design, check out [docs/architecture.md](docs/architecture.md).

## 🕵️ The 5 Agents

| Agent | Role | Tools | Model |
| :--- | :--- | :--- | :--- |
| **Collector** | Gathers data from SEC EDGAR | `get_company`, `list_filings`, `get_financial_summary`, `submit_company_data` | `gpt-4o` |
| **Reconciler** | Mathematical consistency checks | `check_accounting_equation`, `check_yoy_consistency`, `compare_income_vs_cashflow`, `submit_reconciliation` | `gpt-4o` |
| **Quant Analyst** | Forensic fraud models | `compute_beneish_mscore_simplified`, `compute_altman_zscore_simplified`, `compute_accruals_ratio`, `submit_quant_analysis` | `gpt-4o` |
| **Investigator** | Qualitative RAG analysis | `search_disclosures`, `find_related_parties`, `detect_language_patterns`, `submit_investigation` | `gpt-4o-mini` |
| **Supervisor** | Consolidation & scoring | *None (pure reasoning over structured inputs)* | `gpt-4o-mini` |

Every agent follows the **"Submit Tool Pattern"**: they perform their work and eventually call a specific `submit_x` tool. This ensures the output is structured, validated by Pydantic, and ready for the next node in the graph.

The Reconciler and Quant produce **tri-state results** (`passed` / `failed` / `inconclusive`). Missing or unreadable data is always `inconclusive` — it never forces an `ADVERSE` conclusion. Only a genuine accounting-integrity failure (numbers present but the balance sheet provably does not balance) can produce `ADVERSE`.

## 🔬 Data Quality Layer (DQC-Inspired)

SEC EDGAR XBRL data is notoriously inconsistent. Companies frequently tag quarterly revenue with an annual (`fp=FY`) label, omit the annual total entirely, or report incorrect period durations. The ingestion validator catches these issues before any agent sees the data.

### 5 Validation Layers

| Layer | What it checks | DQC reference |
| :--- | :--- | :--- |
| **1. Sign checks** | Revenue, assets, liabilities, share counts must always be positive | DQC Rule 0015 |
| **2. Period duration** | Income statement and cash-flow items must cover 300–400 days (annual) | DQC Rule 0146 |
| **3. Cross-concept** | Cost of revenue must not exceed revenue; gross profit cannot exceed revenue | DQC Rule 0015 family |
| **4. YoY plausibility** | >3× YoY increase or >90% drop triggers a flag on the relevant concept | Inspired by DQC |
| **5. Cross-statement** | Cash flow equation (prior cash + CFO + CFI + CFF ≈ current cash); cash BS vs. CF statement; retained earnings bridge | DQC Rule 0057 |

### Quarterly Aggregation

When a company's 10-K does not tag an annual revenue total (a common DQC Rule 0146 violation), the ingestion pipeline automatically sums Q1 + Q2 + Q3 + Q4 from any available quarterly filings and stores the result with `value_source = "aggregated_4q"`. This prevents partial-quarter figures from silently distorting all downstream models.

### value_source & quality_flag

Every row in `financial_line_items` carries two provenance columns:

| Column | Values | Meaning |
| :--- | :--- | :--- |
| `value_source` | `annual_direct`, `aggregated_4q`, `duration_fallback` | How the value was obtained |
| `quality_flag` | `NULL` (clean), or a string like `duration_mismatch`, `yoy_3x_jump` | What quality issue was detected |

When reading data, the system always prefers clean (`quality_flag IS NULL`) rows and falls back to flagged values only when no clean alternative exists.

## 📊 Evaluation Results
We tested AuditChain against 5 distinct companies (Apple, Tesla, Bausch Health, HP, and Occidental Petroleum).

| Metric | Result |
| :--- | :--- |
| **Recall** | 100% (Caught 100% of known frauds in the set) |
| **Precision** | 50% (Flagged 2 clean companies as high risk) |
| **Accuracy** | 60% |

### Confusion Matrix
| Actual \ Predicted | Flagged (Adverse/Qualified) | Clean (Unqualified) |
| :--- | :---: | :---: |
| **Known Fraud** | 2 (BHC, HPQ) ✓ | 0 |
| **Clean/Healthy** | 2 (TSLA, OXY) ✗ | 1 (AAPL) ✓ |

### Known Limitations

| Limitation | Status |
| :--- | :--- |
| **XBRL concept aliases** — single alias per concept missed standard US-GAAP variants (e.g. Tesla's NCI-inclusive equity tag). Balance sheet could not balance → forced ADVERSE. | ✅ **Fixed**: prioritized alias lists, composition-based derivation, tri-state checks (missing data = inconclusive, never ADVERSE). |
| **XBRL period tagging errors** — quarterly revenue tagged as annual silently corrupted all downstream models (Beneish, YoY). | ✅ **Fixed**: DQC-inspired 5-layer ingestion validator + quarterly aggregation fallback. |
| **Sector-agnostic Altman Z-Score** — the 1968 model was calibrated for manufacturing; it structurally penalizes growth companies and financial institutions. | ✅ **Partially fixed**: SIC-based sector detection gates the Altman score for financial-sector companies (banks, REITs, insurance). Capital-intensive growth companies (semiconductors, EV) remain a known edge case. |
| **Rigid YoY thresholds** — fixed 50% swing thresholds generate noise for cyclical industries. | 🔧 **Planned**: dynamic thresholds informed by S&P sector medians (Planner Agent on roadmap). |
| **Mandatory qualitative flags** — Investigator was forced to flag every filing regardless of evidence, producing false positives for clean companies. | ✅ **Fixed**: evidence-based prompt requires a specific quoted passage before any flag is created; clean investigation is a valid outcome. |

## 🛠️ Tech Stack
| Backend | Frontend |
| :--- | :--- |
| Python 3.12, FastAPI | Next.js 15 (App Router), TypeScript |
| LangGraph, LangChain | Tailwind CSS, shadcn/ui |
| PostgreSQL + pgvector | Framer Motion, Recharts |
| SQLAlchemy 2.0, Pydantic v2 | Lucide Icons, EventSource (SSE) |
| JWT (python-jose), slowapi | |

## 🚀 Getting Started

### Prerequisites
- Python 3.12+ & Node.js 20+
- Docker (for PostgreSQL)
- OpenAI API Key

### Quick Start
1. **Clone and Install**
   ```bash
   git clone <your-repo-url>
   cd auditchain
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e .
   ```

2. **Environment**
   Create a `.env` in the root (see `.env.example` for all options):
   ```env
   # LLM
   OPENAI_API_KEY=your_key_here
   LLM_FAST_MODEL=gpt-4o-mini
   LLM_SMART_MODEL=gpt-4o

   # SEC EDGAR (required — SEC identifies callers by User-Agent)
   SEC_USER_AGENT="Your Name yourname@example.com"

   # Database
   POSTGRES_USER=auditchain
   POSTGRES_PASSWORD=auditchain_dev
   POSTGRES_DB=auditchain
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   DATABASE_URL=postgresql+asyncpg://auditchain:auditchain_dev@localhost:5432/auditchain
   ```

3. **Infrastructure**
   ```bash
   docker compose up -d
   ```
   Then apply the database migrations in order:
   ```bash
   # Run all SQL files in infra/sql/ sequentially
   for f in infra/sql/*.sql; do
     docker exec -i auditchain-postgres psql -U auditchain -d auditchain < "$f"
   done
   ```

4. **Launch**
   ```bash
   # Terminal 1: Backend
   python -m scripts.run_api

   # Terminal 2: Frontend
   cd frontend
   npm install
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000)

## 📁 Project Structure
```text
auditchain/
├── src/auditchain/
│   ├── agents/              # 5 specialized AI agents
│   ├── api/
│   │   ├── events/          # SSE pub/sub (audit + ingestion streaming)
│   │   ├── routers/         # FastAPI routes (auth, companies, audits, ingestion, admin)
│   │   └── services/        # Background task runners
│   ├── auth/                # JWT authentication (access/refresh tokens, user management)
│   ├── core/                # Config, logging, model-aware pricing
│   ├── data/
│   │   ├── ingestion.py     # XBRL ingestion with two-pass annual resolution
│   │   ├── ingestion_validator.py  # DQC-inspired 5-layer quality checks
│   │   └── text_ingestion.py       # SEC text → chunks → embeddings
│   ├── graph/               # LangGraph workflow, state, cost tracking
│   ├── schemas/             # Pydantic contracts (reports, components, enums)
│   └── tools/               # Agent tools (financial data, quantitative, investigation)
├── frontend/                # Next.js 15 application
├── infra/
│   ├── docker/              # Docker Compose configs (dev + prod)
│   └── sql/                 # 14 database migrations (001–014)
├── scripts/                 # CLI utilities
└── docs/                    # Architecture docs & ADRs
```

## 📐 Key Design Decisions
- **Multi-agent over monolithic**: Specialized agents provide better observability, easier debugging, and cost optimization (analytical agents on `gpt-4o`; formatting agents on `gpt-4o-mini`).
- **Pydantic Submit-Tool Pattern**: Guarantees structured data flow between nodes; no fragile regex parsing of LLM markdown.
- **Mark, don't block**: Suspicious XBRL values receive a `quality_flag` and are stored for auditability. The read path always prefers clean values, with flagged ones as a last resort. Data is never silently discarded.
- **Model-aware pricing**: Cost is calculated from the model name the API actually reports on each response — not hardcoded. Changing a model's assignment automatically updates the cost breakdown.
- **pgvector**: Keeps all data in a single source of truth (PostgreSQL) instead of managing a separate vector database.
- **SSE over WebSockets**: Perfect for server-to-client progress updates with zero overhead and automatic reconnection.
- **Deterministic Risk Scoring**: Scores are calculated by a formula (INFO=1 to CRITICAL=25) rather than asking an LLM to guess a number. This ensures reproducibility and auditability.

See [docs/adrs/](docs/adrs/) for detailed Architecture Decision Records.

## 🚧 Roadmap
- [x] **XBRL data quality layer**: DQC-inspired 5-layer validator, quarterly aggregation, quality_flag/value_source provenance.
- [x] **Sector-aware Altman gating**: SIC-based sector detection prevents financial-sector companies from triggering a model calibrated for manufacturing.
- [x] **Evidence-based Investigator**: Qualitative flags require specific quoted evidence from filing text.
- [ ] **Planner Agent**: Dynamic, sector-aware audit strategy with calibrated thresholds.
- [ ] **Advanced XBRL extensions**: Custom taxonomy handling for segment disclosures and non-standard equity structures.
- [ ] **PDF Export**: Generate high-fidelity audit reports for offline review.
- [ ] **Comparative Analysis**: Side-by-side audit of multiple companies.

---

## 👤 Author
Built by **Leonardo P Barretti**  
[lbarretti@gmail.com](mailto:lbarretti@gmail.com) | [LinkedIn](https://www.linkedin.com/in/leonardo-barretti/)

**Interested in a partnership or a technical deep dive?** Reach out via email or LinkedIn. I'm always open to discussing AI agents, forensic finance, and system architecture.

## 📄 License
Released under the [MIT License](LICENSE).
