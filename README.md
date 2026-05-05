# AuditChain 🔍

### A multi-agent AI system that audits SEC filings the way a senior auditor would — except it does it in 2 minutes for $0.30.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-v0.110-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

<!-- TODO: insert screenshot at docs/screenshots/dashboard.png -->

---

## 🚩 The Problem
Forensic analysis of SEC 10-K filings is a nightmare of complexity. You have to verify accounting equations across years, calculate quantitative models like Beneish M-Score and Altman Z-Score, and perform qualitative language analysis across thousands of pages of legalese. 

Big Four firms take days to do this and charge a fortune. Even then, massive frauds like Wirecard, Luckin Coffee, and Wells Fargo escaped detection for years. Human auditors get tired, they miss patterns, and they are expensive. In short: forensic auditing is slow, pricey, and surprisingly fallible.

## 🧠 The Approach
AuditChain explores a simple hypothesis: what if we could build a multi-agent system where each agent is a specialist in one dimension of the audit? 

Coordinated by **LangGraph**, five specialized agents work together in a structured workflow. They don't just "chat"—they use validated tools to extract data, perform math, and search through text via **RAG (pgvector)**. Every decision is grounded in real filing data, and every agent output is validated against strict Pydantic schemas. It’s an automated, high-fidelity forensic pipeline that keeps a full audit trail of its reasoning.

## ✨ What It Does
- **Multi-agent fraud detection pipeline**: Coordinated execution via LangGraph.
- **Real-time progress streaming**: Watch the agents work via Server-Sent Events (SSE).
- **RAG over filing text**: High-density vector search using `pgvector` and `text-embedding-3-small`.
- **Quantitative forensic models**: Automated Beneish M-Score, Altman Z-Score, and Accruals analysis.
- **Self-service company onboarding**: Ingest any of the ~10,000 SEC-registered companies on demand.
- **Persistent audit history**: Every run is stored in a relational database for future review.
- **Professional executive reports**: High-fidelity summaries with deterministic risk scoring.

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
    
    subgraph "AI Audit Engine (LangGraph)"
        API --> LG[Workflow Controller]
        LG --> Collector[Collector Agent]
        LG --> Reconciler[Reconciler Agent]
        LG --> Quant[Quant Analyst Agent]
        LG --> Investigator[Investigator Agent]
        LG --> Supervisor[Supervisor Agent]
    end
    
    Collector -->|Fetch| SEC[SEC EDGAR API]
    Investigator -->|Vector Search| PGV[(PostgreSQL + pgvector)]
    LG -->|LLM Calls| OAI[OpenAI GPT-4o / mini]
    LG -->|Persistence| DB[(PostgreSQL)]

    style LG fill:#f9f,stroke:#333,stroke-width:2px
```

The system uses a stateful graph where agents append their findings to a shared `AuditState`. The **Supervisor** acts as the final judge, consolidating reports and calculating the risk score. For a deeper dive into the "why" behind the design, check out [docs/architecture.md](docs/architecture.md).

## 🕵️ The 5 Agents

| Agent | Role | Tools | Model |
| :--- | :--- | :--- | :--- |
| **Collector** | Gathers data from SEC | `get_company`, `list_filings`, `get_financial_summary`, `submit_company_data` | `gpt-4o-mini` |
| **Reconciler** | Mathematical consistency | `check_accounting_equation`, `check_yoy_consistency`, `compare_income_vs_cashflow`, `submit_reconciliation` | `gpt-4o-mini` |
| **Quant Analyst** | Forensic fraud models | `compute_beneish_mscore_simplified`, `compute_altman_zscore_simplified`, `compute_accruals_ratio`, `submit_quant_analysis` | `gpt-4o-mini` |
| **Investigator** | Qualitative RAG analysis | `search_disclosures`, `find_related_parties`, `detect_language_patterns`, `submit_investigation` | `gpt-4o-mini` |
| **Supervisor** | Consolidation & Scoring | *None (Pure Reasoning)* | `gpt-4o` |

Every agent follows the **"Submit Tool Pattern"**: they perform their work and eventually call a specific `submit_x` tool. This ensures the output is structured, validated by Pydantic, and ready for the next node in the graph.

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

**Why the false positives?** 
AuditChain is aggressive. It correctly identified **Bausch Health (BHC)** and **HP (HPQ)** as adverse due to their known historical accounting issues. However, the Altman Z-Score (a 1968 model) often penalizes capital-intensive growth companies like **Tesla**. Additionally, XBRL parsing can sometimes be tripped up by non-standard equity structures in companies like **Occidental**. A sample size of 5 isn't statistically meaningful, but the failure modes are well-understood and lean towards caution.

## 🛠️ Tech Stack
| Backend | Frontend |
| :--- | :--- |
| Python 3.12, FastAPI | Next.js 15 (App Router), TypeScript |
| LangGraph, LangChain | Tailwind CSS, shadcn/ui |
| PostgreSQL + pgvector | Framer Motion, Recharts |
| SQLAlchemy 2.0, Pydantic v2 | Lucide Icons, EventSource (SSE) |

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
   Create a `.env` in the root:
   ```env
   OPENAI_API_KEY=your_key_here
   SEC_USER_AGENT="Your Name yourname@example.com"
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/auditchain
   ```

3. **Infrastructure**
   ```bash
   docker compose up -d
   # Wait for DB to be ready, then:
   # (Schema is automatically handled or run infra/sql/001_init.sql)
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
├── src/auditchain/          # Backend Python
│   ├── agents/              # 5 specialized AI agents logic
│   ├── api/                 # FastAPI routes + SSE streaming
│   ├── data/                # SQLAlchemy models & Ingestion
│   ├── graph/               # LangGraph workflow & state
│   ├── schemas/             # Pydantic data structures
│   └── tools/               # Custom tools used by agents
├── frontend/                # Next.js 15 application
├── infra/                   # Docker config & SQL migrations
├── scripts/                 # Data ingestion & CLI utilities
└── docs/                    # Architecture docs & ADRs
```

## 📐 Key Design Decisions
- **Multi-agent over Monolithic**: Specialized agents provide better observability, easier debugging, and lower cost (via gpt-4o-mini).
- **Pydantic Submit-Tool Pattern**: Guarantees structured data flow between nodes; no fragile regex parsing of LLM markdown.
- **pgvector**: Keeps all data in a single source of truth (PostgreSQL) instead of managing a separate vector database.
- **SSE over WebSockets**: Perfect for server-to-client progress updates with zero overhead and automatic reconnection.
- **Deterministic Risk Scoring**: Scores are calculated by a formula (INFO=1 to CRITICAL=25) rather than asking an LLM to guess a number. This ensures reproducibility.

See [docs/adrs/](docs/adrs/) for detailed Architecture Decision Records.

## 🚧 Roadmap
- [ ] **Planner Agent**: For sector-aware audit strategies.
- [ ] **Advanced XBRL Parser**: Better handling of custom equity and complex GAAP extensions.
- [ ] **PDF Export**: Generate high-fidelity audit reports for offline review.
- [ ] **Comparative Analysis**: Side-by-side audit of multiple companies.

---

## 👤 Author
Built by **Leonardo P Barretti**  
[lbarretti@gmail.com](mailto:lbarretti@gmail.com) | [LinkedIn](https://www.linkedin.com/in/leonardo-barretti/)

## 📄 License
Released under the [MIT License](LICENSE).
