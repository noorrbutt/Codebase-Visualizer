# Codebase Visualizer

![CI](https://github.com/noorrbutt/Codebase-Visualizer/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Node](https://img.shields.io/badge/node-18%2B-339933.svg)

A small AI-powered GitHub repository analyzer that builds a repository dependency graph, runs per-file AI analysis, and presents an interactive force-directed graph in the browser. Point it at any public GitHub repository and it will fetch source files, parse imports to build a graph, request file-level AI insights, and expose a dashboard with charts and a file viewer.

> Repo: https://github.com/noorrbutt/Codebase-Visualizer

**This project is intended as a portfolio backend+frontend demo.** It shows backend services for crawling and analyzing code, background AI processing, and a React-based interactive visualization frontend. It supports only public GitHub repositories (no authentication flows or private repo access are implemented).

## Demo

| Dashboard & Overview |
<img width="2516" height="1175" alt="image" src="https://github.com/user-attachments/assets/82c870a9-45e9-4a2b-9c79-e5d0c1f263bd" />

<img width="2499" height="1194" alt="image" src="https://github.com/user-attachments/assets/c7ce0cc2-8b4c-46c8-b25a-9ad669798f8c" />


| Graph walkthrough |
<img width="2508" height="1190" alt="image" src="https://github.com/user-attachments/assets/8cb8b6a3-9e4a-453f-bfbc-226427695755" />


|File detail panel |
<img width="2516" height="1183" alt="image" src="https://github.com/user-attachments/assets/ce622770-40d6-4e58-93d9-aa883fdb7480" />

<img width="2522" height="1179" alt="image" src="https://github.com/user-attachments/assets/f9f98a58-a573-4a2f-9b71-ed7cc9492fc1" />



## How it works

1. **Fetch** — Given a GitHub URL, the backend resolves the default branch, walks the repo tree via the GitHub API, and filters to supported source extensions (skipping `static/`, `migrations/`, `docs/`, oversized files, etc.).
2. **Parse** — Each file's imports are extracted (`app/services/parser.py`) and normalized into a shared module-path format.
3. **Resolve** — Relative and absolute imports are resolved against a module map to build directed edges between files (`_build_edges` / `_resolve_relative_import` in `app/api/routes/repos.py`), handling `./`, `../`, and index-file imports.
4. **Analyze** — Each file (and the repo as a whole) is optionally summarized by an LLM (Groq) with role/complexity classification, budget-limited per client and globally.
5. **Coordinate** — Repo analyses run as background tasks behind a Redis-backed concurrency gate and per-repo lock, so the same repo can't be analyzed twice at once and a crashed worker's in-flight analyses are safely reclaimed on restart.
6. **Visualize** — The React frontend renders the resulting nodes/edges as an interactive force-directed graph (Canvas-based), plus charts for language breakdown, complexity, and file roles.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, Alembic, Redis (coordination + rate limiting)
- **AI:** Groq-hosted LLM via the project's AI service wrapper
- **Frontend:** React, Vite, Canvas API (force-directed graph rendering)
- **Database:** SQLite for local dev, PostgreSQL recommended for production
- **Testing:** pytest (backend)

## Features

- Interactive dependency graph (force-directed) with pan / zoom / drag
- Per-file AI analysis: role classification, complexity estimate, short summary
- Language breakdown charts and simple metrics (line counts, import counts)
- File role classification and file source viewer
- Redis-backed per-repo locking, concurrency caps, and crash-safe analysis resumption
- IP-based rate limiting and per-client/global AI usage budgets

## Project structure

```
Codebase-Visualizer/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # repos.py (analyze/list/get), files.py (per-file AI analysis)
│   │   ├── services/         # github.py, parser.py, ai.py, rate_limit.py, coordination.py
│   │   ├── models/           # SQLAlchemy models: Repository, FileNode, FileEdge
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── main.py           # app factory, lifespan, exception handlers, /health
│   │   └── config.py         # env-driven Settings
│   ├── alembic/               # DB migrations
│   ├── tests/                  # pytest suite
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/graph/   # GraphView.jsx — force-directed canvas renderer
        ├── components/charts/  # language/complexity/role charts
        ├── components/panels/  # file list + node detail panels
        ├── hooks/useForceGraph.js
        └── utils/api.js        # fetch wrapper (adds X-API-Key header)
```

## Setup

These steps assume a development machine with Python 3.10+, Node.js 18+, and Redis installed.

### 0. Start Redis

The backend requires Redis for rate limiting and repo-analysis coordination — it will not start without a reachable instance.

```bash
# macOS (Homebrew)
brew install redis && brew services start redis

# Docker (any OS)
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Confirm it's reachable: `redis-cli ping` should return `PONG`.

### 1. Backend

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Copy and populate environment variables:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set GROQ_API_KEY (required for AI features).
# Optionally set GITHUB_TOKEN to raise GitHub's unauthenticated 60 req/hr limit to 5000 req/hr.
```

Initialize the database and run migrations:

```bash
cd backend
alembic upgrade head
```

Run the development server:

```bash
uvicorn app.main:app --reload
```

The API is now live at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

Background tasks perform AI analysis and repository summarization asynchronously — large repositories may take a while to finish processing; poll `GET /repos/{id}/status` to track progress.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the Vite dev server (usually `http://localhost:5173`). Set `VITE_API_URL` in `frontend/.env` if the backend runs on a different host/port.

The frontend does not rely on a secret client-side credential — browser code is public, so abuse control comes from backend IP rate limiting rather than a client-side API key. When `API_KEY` is configured, repo read endpoints also require the same `X-API-Key` header sent by the browser.

## API reference

Full interactive schema is available at `/docs` once the backend is running. Summary:

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/repos/analyze` | Queue analysis of a public GitHub repo (`{"github_url": "..."}`). Returns the created repo record; graph data populates asynchronously. | `X-API-Key` (if `API_KEY` is set) |
| `GET` | `/repos/` | List all previously analyzed repositories. | `X-API-Key` (if `API_KEY` is set) |
| `GET` | `/repos/{repo_id}` | Fetch a repo's full graph (nodes + edges) and status. | `X-API-Key` (if `API_KEY` is set) |
| `GET` | `/repos/{repo_id}/status` | Poll analysis status (`parsing` / `ready` / `failed`). | `X-API-Key` (if `API_KEY` is set) |
| `POST` | `/files/analyze` | Trigger/retrieve AI analysis (summary, complexity, role) for a single file in an analyzed repo. | `X-API-Key` (if `API_KEY` is set) |
| `GET` | `/health` | Liveness check. | none |
| `GET` | `/health/ready` | Readiness check — verifies DB and Redis connectivity. | none |

Example:

```bash
curl -X POST http://localhost:8000/repos/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $VITE_API_KEY" \
  -d '{"github_url": "https://github.com/octocat/Hello-World"}'
```

## Testing

```bash
cd backend
pytest
```

The suite covers import parsing (`test_parser.py`, `test_import_resolution.py`), rate limiting and AI budget enforcement (`test_protection_limits.py`), AI service behavior (`test_ai.py`), production config guards (`test_config_guard.py`), and the repo analysis API (`test_repos.py`). Tests inject fake Redis clients rather than requiring a live instance — no external services needed to run them.

## Environment variables

| Name | Required | Description |
|------|----------|-------------|
| `GROQ_API_KEY` | Yes | API key for the Groq LLM used for file and repo analysis. Without this the AI features will fail. |
| `DATABASE_URL` | No | Database connection string. Defaults to a local SQLite file. Production deployments should point this to PostgreSQL — SQLite will not handle concurrent background writes well. |
| `REDIS_URL` | No | Redis connection string for rate limiting and repo-analysis coordination. Defaults to `redis://localhost:6379/0`. |
| `GITHUB_TOKEN` | No | Optional GitHub Personal Access Token — raises GitHub API rate limits from 60/hr to 5000/hr. |
| `API_KEY` | No | Server-side key required on `X-API-Key` for repo read/write endpoints when set. Not a real secret once shipped to the browser — deters casual abuse only; pair with infra-level rate limiting in production. |
| `VITE_API_URL` | No | Frontend-only backend base URL for local development. Not an auth boundary. |
| `VITE_API_KEY` | No | Sent as `X-API-Key` from the browser; mirrors `API_KEY` if set. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Per-IP request cap for public endpoints. |
| `MAX_REPO_FILES` | No | Cap on files ingested per repository analysis. |
| `MAX_CONCURRENT_REPO_ANALYSES` | No | Global cap on simultaneously running repo analyses. |
| `AI_MAX_REQUESTS_PER_HOUR` / `AI_MAX_REQUESTS_PER_DAY` | No | Global AI request budget. |
| `AI_MAX_CLIENT_REQUESTS_PER_HOUR` / `AI_MAX_CLIENT_REQUESTS_PER_DAY` | No | Per-client AI request budget. Raise locally (e.g. 100 / 200) if repeatedly testing from the same machine. |
| `TRUST_PROXY_HEADERS` | No | Only set `true` behind a trusted reverse proxy that strips/sets `X-Forwarded-For`; otherwise IP rate limiting is trivially bypassed. |

## Limitations & notes

- Only public GitHub repositories are supported; private repos are not.
- Public repository analysis is protected by server-side IP rate limiting, not a frontend-exposed secret.
- AI requests are throttled and run in background tasks — large repositories take time and may hit rate limits.
- No authentication, onboarding, or team/collaboration features are implemented — out of scope for this demo.

## Production deployment

- Don't rely on a frontend-exposed API key for protection — `VITE_API_KEY`/`API_KEY` deters casual abuse only, since it's visible in browser bundles.
- Put `/repos/analyze` behind infrastructure-level rate limiting (Cloudflare, nginx `limit_req`, WAF/CDN rules).
- Only set `TRUST_PROXY_HEADERS=true` behind a trusted reverse proxy that strips client-supplied `X-Forwarded-For`.
- Set a `GITHUB_TOKEN` to avoid the unauthenticated 60 req/hr GitHub limit.
- Use PostgreSQL via `DATABASE_URL`, not the default SQLite file.

## Contributing

Issues and pull requests are welcome. Please run `pytest` (backend) and `npm run lint` (frontend) before submitting.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
