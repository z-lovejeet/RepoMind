# RepoMind

**AI-Powered Repository Intelligence System**

Upload a GitHub repository and ask questions about its codebase. Get answers grounded in actual source code with file citations.

## Features

- 🔍 **Repository Ingestion** — Clone any public GitHub repo or upload a zip
- 🧠 **RAG Pipeline** — Retrieval-Augmented Generation with hybrid search
- 💬 **Code Q&A** — Ask natural language questions, get grounded answers
- 📊 **Code Intelligence** — Dependency graphs, reference finding
- 🧪 **Experiments** — A/B compare retrieval strategies (Dense, BM25, Hybrid, HyDE)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript |
| Backend | FastAPI (Python) |
| Auth | Firebase Authentication (Google + GitHub) |
| Database | Cloud Firestore |
| Storage | Firebase Storage |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Vector Search | FAISS |
| Keyword Search | BM25 |
| LLM | OpenAI GPT-4o-mini / Ollama |
| Deployment | Render (backend) + Cloudflare Pages (frontend) |

## Project Structure

```
RepoMind/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── main.py            # App entry + health endpoint
│   │   ├── config.py          # Pydantic Settings
│   │   ├── core/              # RAG Engine
│   │   │   ├── ingestion/     # Clone repos, scan files
│   │   │   ├── parsing/       # AST parsing, doc parsing
│   │   │   ├── chunking/      # Code/doc/text chunkers
│   │   │   ├── embedding/     # Sentence Transformers
│   │   │   ├── indexing/      # FAISS + BM25
│   │   │   ├── retrieval/     # Dense, hybrid, HyDE, reranking
│   │   │   ├── generation/    # LLM client, prompts, parsing
│   │   │   └── analysis/      # Dependency graph, references
│   │   ├── api/               # REST endpoints
│   │   ├── middleware/        # Firebase JWT auth
│   │   ├── models/            # Pydantic schemas
│   │   └── services/          # Firebase Admin SDK
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   # React + Vite
│   ├── src/
│   │   ├── pages/             # Landing, Dashboard, RepoChat, Experiments
│   │   ├── components/        # Auth, Chat, Repo, Analysis, UI
│   │   ├── hooks/             # useAuth, useRepos, useChat
│   │   ├── lib/               # Firebase, API client, constants
│   │   ├── types/             # TypeScript interfaces
│   │   └── styles/            # Global CSS design system
│   ├── package.json
│   └── .env.example
│
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Firebase project with Auth, Firestore, and Storage enabled
- OpenAI API key (or Ollama for local LLM)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Firebase and OpenAI credentials

# Run
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env
# Edit .env with your Firebase client config

# Run
npm run dev
```

### Verify

```bash
# Backend health check
curl http://localhost:8000/api/health

# Frontend
open http://localhost:5173
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Project Setup | ✅ | Directory structure, FastAPI, React, Firebase |
| 2. Ingestion Pipeline | ⬜ | Git clone, file scanning, encoding |
| 3. Parsing & Chunking | ⬜ | AST parsing, chunking strategies |
| 4. Embedding & Indexing | ⬜ | Sentence Transformers, FAISS, BM25 |
| 5. Basic Retrieval | ⬜ | Dense and BM25 search |
| 6. Generation & Pipeline | ⬜ | LLM integration, end-to-end RAG |
| 7. API Layer & Auth | ⬜ | REST endpoints, Firebase JWT |
| 8. Frontend Foundation | ⬜ | Auth UI, dashboard, repo management |
| 9. Chat & Streaming | ⬜ | SSE streaming, chat interface |
| 10. Deployment | ⬜ | Render + Cloudflare Pages |
| 11. Advanced Retrieval | ⬜ | Hybrid (RRF), HyDE, reranking |
| 12. Code Intelligence | ⬜ | Dependency graphs, references |
| 13. Experiments | ⬜ | A/B comparison UI |
| 14. Production Hardening | ⬜ | Logging, rate limiting, security |

## License

MIT
