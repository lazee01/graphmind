# GraphMind — Evidence-first scientific literature QA

GraphMind is a runnable B.Tech prototype for asking questions over scientific literature. This repository now contains a FastAPI backend and a responsive React/Vite research console. The original portfolio visual components remain in `src/SpaceScene.tsx` for reuse.

The default local engine is intentionally dependency-light: it extracts PDF/TXT/Markdown text, detects sections, creates overlapping provenance-aware chunks, indexes them with a deterministic TF-IDF vector fallback, blends lexical and semantic scores, builds a lightweight local relationship graph, and returns citation metadata plus an explicit confidence/status. The model adapter (`backend/app/providers.py`) can activate Sentence Transformers embeddings, Hugging Face generation/summarization/NER, or an OpenAI-compatible API for planning, answer generation, and verification when configured; every adapter catches missing packages/model downloads and falls back explicitly.

For the report-aligned production path, `backend/requirements-optional.txt` lists Sentence Transformers/Hugging Face, PyTorch, FAISS, Neo4j, LangChain, and PyMuPDF. These are intentionally opt-in because their native/runtime footprints are large; the API contracts do not change when a stronger provider is introduced. QLoRA is an experimentation path for fine-tuning a compatible local generator, not a requirement for this retrieval MVP. No credentials are committed.

## Run the full prototype

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API stores its local index in `backend/data` by default. Copy `.env.example` to `.env` to configure `GRAPHMIND_DATA_DIR` and `GRAPHMIND_MODEL_PROVIDER` (`local`, `huggingface`, `sentence-transformers`, or `openai-compatible`). `GET /api/health` and `GET /api/config` report the selected models and whether a model adapter is active. Useful endpoints are `GET /api/health`, `GET /api/config`, `GET /api/documents`, `POST /api/documents`, and `POST /api/ask`.

### Frontend

## Local development

```bash
npm install
npm run dev
```

Vite serves the GraphMind console at the displayed local URL. Set `VITE_API_URL` when the API is hosted elsewhere; otherwise it uses `http://127.0.0.1:8000`.

If the API is unavailable, the Pages frontend automatically switches to **Offline Demo Mode**. It provides a seeded scientific-literature corpus, grounded sample answer, evidence/citations, provider status, and simulated upload/query interactions so the published UI remains explorable. This mode is clearly labeled and does not imply that a backend or model is running.

The Pages workflow reads the optional GitHub repository variable `VITE_API_URL` at build time. Set it to the deployed Render API URL (for example `https://graphmind-api.onrender.com`) under **Settings → Secrets and variables → Actions → Variables**. If unset, the public frontend intentionally remains in Offline Demo Mode until it can reach the default local API.

## Tests

```bash
cd backend
pytest -q
cd ..
npm run typecheck
npm run build
```

The demo corpus is inserted automatically on first backend start, so the query and evidence workflow is usable immediately. PDF extraction depends on `pypdf`; scanned/image-only PDFs need OCR, which is deliberately not claimed by this MVP.

The model integrations use pretrained configurable models; none are trained in this repository. Fine-tuning/QLoRA requires a prepared dataset, a compatible base model, GPU resources, and a separate training workflow.

The backend orchestration contract coordinates planner, retrieval, graph/entity, verifier, and generator agents as structured messages (`plan→retrieve→graph→fuse→verify→generate`). In local mode these are deterministic fallback agents; real model-backed calls require a user-supplied provider configuration and a hosted/running backend. The public Pages deployment intentionally uses Offline Demo Mode because GitHub Pages cannot run FastAPI or protect model API keys.

## Docker

The backend can also run with `docker compose up --build`; persistent indexed data is kept in the `graphmind-data` volume. Keep the Vite frontend on the host with `npm run dev`, or build it separately and set `VITE_API_URL` to the published API URL.

## One-click Render backend deployment

1. Open Render and choose **New → Blueprint**, then select this repository. Render detects `render.yaml` and creates the `graphmind-api` Docker web service.
2. Set the prompted `GRAPHMIND_CORS_ORIGINS` value to `https://lazee01.github.io` (add `http://localhost:5173` for local development). Render supplies `PORT`; the Docker command binds to it automatically.
3. The blueprint mounts a 1 GB persistent disk at `/var/data`, where `GRAPHMIND_DATA_DIR` stores the local index. The free plan may sleep and has provider/runtime limits.
4. After deployment, verify `https://<service>.onrender.com/api/health`, then save that URL as the GitHub Actions repository variable `VITE_API_URL` and rerun the Pages workflow.

No API keys are included. Add model credentials such as `GRAPHMIND_LLM_API_KEY` only in Render's environment settings. Final Render account authorization, service creation, and AI provider key entry require the repository owner.

Create a production build with `npm run build`, then preview it with `npm run preview`.

## Deploy to GitHub Pages

1. Push the repository to GitHub.
2. In **Settings → Pages**, select **GitHub Actions** as the source.
3. The included `.github/workflows/deploy-pages.yml` installs Node, runs `npm ci`, builds the site, and deploys `dist` with the official Pages actions.
4. The committed `public/CNAME` file keeps the custom domain attached to Pages. The Vite base is `/`, which is correct for `rohitpaul.me`.
5. If the first workflow run reports `Creating Pages deployment failed: Not Found`, enable Pages once in **Settings → Pages** with **Source: GitHub Actions**, then rerun the workflow. This is a repository setting rather than a code or credential requirement.

The downloadable CV is kept at `public/rohit-paul-cv.txt` and is copied to the site root during the build.

## Namecheap custom domain: rohitpaul.me

In the repository's **Settings → Pages → Custom domain**, enter `rohitpaul.me`. Commit the generated `CNAME` file if GitHub creates one, or add `public/CNAME` containing:

```text
rohitpaul.me
```

In Namecheap, open **Advanced DNS** for `rohitpaul.me` and create these records (remove conflicting URL redirect and parking records):

| Type | Host | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `lazee01.github.io` |

DNS propagation can take up to 48 hours. Once GitHub Pages verifies the domain, enable **Enforce HTTPS**.

## Content notes

The site uses only the supplied CV details. GitHub and LinkedIn links are intentionally generic placeholders because profile URLs were not included; replace them in `src/main.jsx` when available.
