# 🧠 GraphMind AI — Enterprise Scientific Intelligence & Autonomous Research Agent

[![Live App](https://img.shields.io/badge/Live_App-web--graphmind.web.app-06b6d4?style=for-the-badge&logo=firebase)](https://web-graphmind.web.app)
[![Backend API](https://img.shields.io/badge/API_Engine-Render_Cloud-22c55e?style=for-the-badge&logo=fastapi)](https://graphmind-api-zhrf.onrender.com/api/health)
[![License](https://img.shields.io/badge/Stage-Production_Ready-3b82f6?style=for-the-badge)](#)

**GraphMind AI** is a production-ready Scientific Literature QA, Knowledge Graph Reasoning, and Multi-Model AI Agent platform built for researchers, engineers, and enterprise teams.

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
- **RAG + Knowledge Graph + Frontier LLM Synthesis**: Combines grounded literature passages with entity-relationship graph traversal (`Neo4j AuraDB` + deterministic local graph fallback) and deep technical reasoning.

### 3. 💬 Autonomous AI Agent Chat
- **Multi-Turn Conversational Memory**: Full ChatGPT/Gemini-style multi-turn conversation threads with persistent local & cloud-synced session history.
- **Multi-Provider Model Cascade**:
  - **OpenAI GPT-OSS 120B** & **Qwen 3.8 27B** (via Groq LPUs)
  - **Google Gemini 3.8 Flash**
  - **Hugging Face Transformers** (`all-MiniLM-L6-v2` embeddings & `dslim/bert-base-NER`)
  - **Deterministic Local Fallback** (zero-dependency offline safety)

### 4. 🔐 Enterprise Authentication & Account Dashboard
- **8 Authentication Flows**:
  - 📧 **Email & Password** (Firebase Auth + SQLite PBKDF2-SHA256)
  - 🆕 **Instant Registration** with auto-login
  - 🔵 **Google OAuth 2.0** (`google.com` IdP)
  - ⌥ **GitHub & ⊞ Microsoft OAuth**
  - ✨ **Passwordless Magic Email Link**
  - 📲 **Device / Phone OTP** (real-time 6-digit OTP delivered to user's phone/PC/tablet via Gmail SMTP)
  - 🔑 **Password Reset**
  - ⚡ **Instant Guest Session**
- **Interactive Account Panel**: Click your profile badge in the top navigation bar to view your account provider badge, message & document statistics, active AI engine telemetry, feature status, and recent conversation threads.

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
| `GRAPHMIND_MODEL_PROVIDER` | Primary provider (`groq`, `gemini`, `huggingface`, or `local`) |
| `GRAPHMIND_PROVIDER_SLOTS` | Cascade order: `groq,gemini,huggingface,local` |
| `GRAPHMIND_GENERATION_MODEL` | Default LLM (`openai/gpt-oss-120b`) |
| `GRAPHMIND_GROQ_API_KEY` | Groq API key for GPT-OSS 120B & Qwen 3.8 |
| `GRAPHMIND_GEMINI_API_KEY` | Google Gemini API key (`gemini-3.8-flash`) |
| `GRAPHMIND_HUGGINGFACE_API_KEY` | Hugging Face Hub token for embeddings & NER |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | Neo4j AuraDB cloud knowledge graph credentials |
| `OTP_SMTP_FROM` / `OTP_SMTP_PASSWORD` | Gmail SMTP address & App Password for real OTP delivery |

---

## 📦 Deployment Commands

```bash
# Build production frontend bundle
npm run build

# Deploy frontend to Firebase Hosting (web-graphmind.web.app)
firebase deploy --only hosting:web-graphmind --project graphmind-001
```
