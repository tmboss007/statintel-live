# StatIntel — Workforce Intelligence & Cadre Competency Platform

[![Render Live](https://img.shields.io/badge/Render-Live%20Deployment-00c7b7?logo=render&logoColor=white)](https://statintel-live.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Groq AI](https://img.shields.io/badge/Groq-Llama%20%2F%20Qwen%20Inference-f55036)](https://groq.com)
[![ReportLab](https://img.shields.io/badge/PDF%20Dossier-ReportLab-red)](https://www.reportlab.com)

**StatIntel** is a full-stack, enterprise-grade Workforce Intelligence & Cadre Competency Development Platform tailored for National Statistical Systems, government directorates, and data-driven public organizations. It combines population-level mathematical statistics, automated gap-severity modeling, an interactive 3-Layer Neural Competency Topology, and a signature **Plan My Pathway** curriculum engine with accredited educational video repositories.

🌐 **Live Application**: [https://statintel-live.onrender.com](https://statintel-live.onrender.com)  
🔑 **Demo Credentials**: Username: `admin` | Password: `ChangeMe-Now-123!`

---

## 🌟 Key Capabilities & System Highlights

### 1. Population-Level Mathematical Diagnostics
- Computes sample and population-level indicators across all officers: Mean ($\mu$), Median, Mode, Variance, Standard Deviation ($\sigma$), Fisher-Pearson Skewness, Excess Kurtosis, Interquartile Range (IQR), and Coefficient of Variation (CV).
- Interactive readiness histograms with Gaussian normal distribution overlays.
- Dynamic Department $\times$ Skill competency heatmaps with real-time cell filtering.

### 2. Multi-Factor Gap Severity Engine
Ranks organizational skill deficiencies using an evidence-based logarithmic formulation:
$$\text{Severity} = (\text{Mention Ratio} \times 60) + (\text{Log-Scaled Impact} \times 40)$$
where:
$$\text{Mention Ratio} = \frac{\text{Profiles with Skill Gap}}{\text{Total Profiles}}$$
$$\text{Log-Scaled Impact} = \min\left(1.0, \frac{\ln(\text{Gap Count} + 1)}{\ln(\text{Total Profiles} + 1)}\right)$$

### 3. Differentiated "Plan My Pathway" Curriculum Engine
- **Cadre-Tier Calibration**: Automatically classifies officers into **Operational**, **Senior**, or **Executive** tiers.
- **Dynamic Milestones**: Generates cadre-appropriate practical projects:
  - *Operational*: Clean census microdata using Pandas & Fellegi-Holt consistency rules.
  - *Senior*: Implement X-13ARIMA-SEATS seasonal adjustments & stratified multi-stage probability sampling.
  - *Executive*: Econometric policy evaluation (DID, Instrumental Variables) and national data governance.
- **Verified Video Catalog**: 25 active, allowlisted educational lectures (MIT OpenCourseWare, Corey Schafer, StatQuest, Stanford Online, freeCodeCamp, Luke Barousse).
- **PDF Export Dossier**: Generates publication-ready, multi-page vector PDF dossiers using ReportLab with officer readiness breakdowns and milestone checklists.

### 4. Hybrid AI Copilot & Grounded Cadre Advisor
- Powered by **Groq ultra-fast Llama / Qwen inference** (~0.6s response latency).
- **Zero-Failure Architecture**: Features a deterministic, mathematical fallback engine that delivers accurate, civil-service-aligned career progression dossiers even when offline or without API keys.

### 5. Interactive 3-Layer Neural Competency Topology
- Canvas-based SVG neural graph visualizing relationships between **Cadre Roles**, **Competency Skills**, and **Learning Modules**.
- Real-time synapse pulse animations showing forward-activation flows from current post to target promotion rank.

---

## 🛠️ Architecture & Tech Stack

```mermaid
graph TD
    Client["Client Browser (Vanilla HTML5 / Modern CSS / Chart.js / SVG Canvas)"]
    FastAPI["FastAPI Application Server (Python 3.12 / Uvicorn)"]
    Engine["Analytics & Mathematical Diagnostics Engine"]
    Pathway["Pathway Engine & Video Curator"]
    DB[("PostgreSQL 16 / SQLite Engine")]
    Groq["Groq Llama / Qwen API"]
    PDF["ReportLab Vector PDF Generator"]

    Client <-->|REST API / JWT| FastAPI
    FastAPI <--> DB
    FastAPI --> Engine
    FastAPI --> Pathway
    Pathway --> Groq
    Pathway --> PDF
```

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Backend Core** | Python 3.12, FastAPI 0.115 | High-performance asynchronous REST API |
| **ORM & Database** | SQLAlchemy 2.0, Psycopg 3 | PostgreSQL (Cloud Production) & SQLite (Local Dev) |
| **Security & Auth** | JWT (HS256) + Argon2-cffi | Role-Based Access Control (`admin`, `officer`, `viewer`) |
| **Analytics Engine** | Python `statistics`, `math` | Pure mathematical descriptive stats and severity modeling |
| **AI Inference** | Groq API (`qwen/qwen3.8-27b`) | Sub-second career copilot & conversational advisory |
| **Reporting** | ReportLab 5.0 | Vector-grade PDF generation with tables and typography |
| **Frontend UI** | HTML5, CSS3, JavaScript (ES6+) | Zero-dependency, lightweight, ultra-responsive UI |
| **Visualizations** | Chart.js 4.4, SVG Neural Network | Radar charts, histograms, heatmaps, doughnut charts |
| **Cloud Hosting** | Render Web Service + Managed PostgreSQL | Continuous deployment from GitHub |

---

## 🚀 Quick Start Guide

### 1. Local Development (SQLite)

```bash
# Clone the repository
git clone https://github.com/tmboss007/statintel-live.git
cd statintel-live

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Start the application server
uvicorn backend.app.main:app --reload --port 8000
```
Visit **`http://localhost:8000`** in your browser. Default Admin: `admin` / `ChangeMe-Now-123!`

---

### 2. Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```env
# Application Settings
SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ChangeMe-Now-123!
SEED_DEMO_DATA=true

# Database (Leave blank for SQLite, or provide PostgreSQL connection string)
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname

# Optional: Groq AI Ultra-Fast Inference
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=qwen/qwen3.8-27b
```

---

## 📊 Stress-Testing with 50-Officer Dataset

The repository includes [`statintel_50_officers_dataset.csv`](file:///e:/GNITC%20Hydrabad/Statintel/statintel_50_officers_dataset.csv) featuring 50 officers distributed across 8 departments and 7 statistical cadres.

To test large-scale workforce data processing:
1. Log in to the application.
2. Navigate to **Officer Directory** &rarr; **Import CSV**.
3. Select `statintel_50_officers_dataset.csv` and upload.
4. Observe the instantaneous re-computation of population statistics, skewness, kurtosis, and department heatmaps.

---

## 📑 API Endpoints Summary

| Method | Endpoint | Description | Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System status, database health, record counts | Public |
| `POST` | `/api/auth/login` | Officer / Admin authentication, returns JWT | Public |
| `GET` | `/api/dashboard/stats` | Executive KPI summary and high-level distributions | Token |
| `GET` | `/api/analytics/descriptive` | Population statistics ($\mu, \sigma$, skewness, kurtosis) | Token |
| `GET` | `/api/analytics/heatmap` | Department $\times$ Skill competency matrix | Token |
| `POST` | `/api/pathway/generate` | Generate differentiated cadre learning roadmap | Token |
| `POST` | `/api/pathway/converse` | Grounded multi-turn conversational advisory | Token |
| `POST` | `/api/pathway/export-pdf` | Download official ReportLab PDF learning dossier | Token |
| `POST` | `/api/ai/career-copilot` | AI career transition and competency gap copilot | Token |
| `POST` | `/api/officers/import-csv` | Bulk officer import with validation | Admin |

Interactive OpenAPI documentation is available live at [`/docs`](https://statintel-live.onrender.com/docs).

---

## 🔒 Security & Governance

- **Password Storage**: Argon2id cryptographic hashing with automatic salt generation.
- **Session Integrity**: Ephemeral JSON Web Tokens with configurable expiration (`TOKEN_MINUTES`).
- **Audit Logging**: Immutable audit logs capturing every state change (role modification, access authorization, bulk imports).
- **Resilient Connectivity**: Automatic driver normalization (`postgres://` &rarr; `postgresql+psycopg://`) and graceful fallback guards preventing connection-string injection or dialect misconfigurations.

---

## 📜 License & Acknowledgments

Developed for the **Ministry of Statistics and Programme Implementation (MoSPI)** workforce development initiatives and statistical cadre excellence.  
Designed under modern Open Statistical Standards (UNSD, ISI Kolkata, Eurostat).
