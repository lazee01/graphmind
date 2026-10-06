# 🧠 GraphMind AI — Scientific Literature QA MVP

[![Live App](https://img.shields.io/badge/Live_App-web--graphmind.web.app-06b6d4?style=for-the-badge&logo=firebase)](https://web-graphmind.web.app)
[![Backend API](https://img.shields.io/badge/API_Engine-Render_Cloud-22c55e?style=for-the-badge&logo=fastapi)](https://graphmind-api-zhrf.onrender.com/api/health)
[![License](https://img.shields.io/badge/Stage-MVP%2FBeta-3b82f6?style=for-the-badge)](#)

**GraphMind AI** is an MVP/beta Scientific Literature QA prototype for uploading papers, asking grounded questions, and reviewing evidence and provenance. External providers and persistence are optional and deployment-dependent.

---

## 🌐 Live Deployments

| Surface | URL | Status |
| :--- | :--- | :--- |
| **Primary Web App (Firebase Hosting)** | **[https://web-graphmind.web.app](https://web-graphmind.web.app)** | 🟢 Live |
| **Mirror Web App (FirebaseApp)** | **[https://web-graphmind.firebaseapp.com](https://web-graphmind.firebaseapp.com)** | 🟢 Live |
| **FastAPI Backend Engine (Render)** | **[https://graphmind-api-zhrf.onrender.com/api/health](https://graphmind-api-zhrf.onrender.com/api/health)** | 🟢 Live |

---

## ✨ Core Capabilities

### 1. 🔬 Literature RAG (Primary Mode)
- **Evidence-First Scientific QA**: Extracts text from PDF, TXT, and Markdown research papers, detects document sections, and builds overlapping provenance-aware chunks (`page`, `section`, `document_name`, `chunk_id`).
- **Hybrid Retrieval**: Blends lexical TF-IDF matching with semantic vector embeddings (`sentence-transformers/all-MiniLM-L6-v2`) to maximize both precision and recall.
- **Inline Citations & Confidence Scoring**: Every claim is grounded in retrieved passages with verifiable inline citations and automated verifier confidence scores.

### 2. ⚡ Hybrid Research AI
- **RAG + Knowledge Graph + Configurable Generation**: Combines grounded literature passages with entity-relationship graph traversal (`Neo4j` is optional) and a deterministic local graph fallback.

### 3. 💬 Research Chat
- **Local browser thread history**: The frontend can keep recent threads in browser storage. Cloud-synced memory is not guaranteed by this MVP.
- **Multi-Provider Model Cascade**:
  - **Groq/OpenAI-compatible generation** (active on the current Render deployment)
  - **Local Hugging Face Transformers** when optional packages and model files are installed
  - **Gemini native API is not implemented in the current adapter**
  - **Deterministic Local Fallback** (zero-dependency offline safety)

### 4. 🔐 Beta Authentication
- Email/password and optional Firebase sign-in surfaces are present, but provider setup, OAuth credentials, OTP delivery, and account persistence depend on external configuration. Do not treat every UI option as enabled in every deployment.

---

## 🏗️ Multi-Agent Architecture

GraphMind coordinates 5 specialized agents in an explicit pipeline (`plan → retrieve → graph → fuse → verify → generate`):

1. **Planner Agent**: Decomposes complex research questions into targeted sub-queries and extracts key scientific entities.
2. **Retriever Agent**: Executes hybrid vector + lexical search across the indexed document library (with optional single-document scoping).
3. **Graph Reasoning Agent**: Traverses subject–predicate–object triples in Neo4j AuraDB / local graph store to surface multi-hop relationships.
4. **Generator Agent**: Synthesizes grounded answers with inline citations or multi-turn conversational responses.
5. **Verifier Agent**: Audits generated answers against retrieved evidence passages and computes a calibrated confidence score.

---

## 🚀 Quick Start (Local Development)

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend (React 19 + TypeScript + Vite)

```bash
npm install
npm run dev
```

### 3. Run Verification Suite

```bash
cd backend
pytest -q
cd ..
npm run typecheck
npm run build
```

---

## 🔒 Security & Environment Configuration

All `.env` files (`.env` and `backend/.env`) are excluded via `.gitignore` so **raw secret keys are never committed in plain text**.

Configure the following environment variables in `backend/.env` (local) or in your **Render Dashboard → Environment** (production):

| Variable | Description |
| :--- | :--- |
| `GRAPHMIND_MODEL_PROVIDER` | `groq`, `openai-compatible`, `huggingface`, `sentence-transformers`, or `local` |
| `GRAPHMIND_PROVIDER_SLOTS` | Optional status slots; local fallback remains available |
| `GRAPHMIND_GROQ_MODEL` | Groq model name; the live service currently reports `openai/gpt-oss-120b` |
| `GRAPHMIND_GROQ_API_KEY` | Rotated Groq API key, stored only in Render |
| `GRAPHMIND_GEMINI_API_KEY` | Not used by the current native adapter |
| `GRAPHMIND_HUGGINGFACE_API_KEY` | Not required by the current local Transformers path |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | Neo4j AuraDB cloud knowledge graph credentials |
| `OTP_SMTP_FROM` / `OTP_SMTP_PASSWORD` | Gmail SMTP address & App Password for real OTP delivery |

---

## 📦 Deployment Commands

```bash
# Build production frontend bundle
npm run build

# Deploy frontend to Firebase Hosting (primary)
firebase deploy --only hosting:web-graphmind --project graphmind-001
```

Firebase primary: [web-graphmind.web.app](https://web-graphmind.web.app). Firebase mirror: [web-graphmind.firebaseapp.com](https://web-graphmind.firebaseapp.com). GitHub Pages mirror: [lazee01.github.io/graphmind](https://lazee01.github.io/graphmind/). Backend: [Render health](https://graphmind-api-zhrf.onrender.com/api/health).

Render Free uses `/tmp/graphmind-data`, which is ephemeral. Uploaded papers, the local index, and SQLite sessions can be lost after a restart or redeploy. Use a paid persistent disk mounted at `/var/data` for retention.
