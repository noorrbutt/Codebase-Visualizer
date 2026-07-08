# Codebase Visualizer

![CI](https://github.com/noorrbutt/Codebase-Visualizer/actions/workflows/ci.yml/badge.svg)

A small AI-powered GitHub repository analyzer that builds a repository dependency graph, runs per-file AI analysis and presents an interactive force-directed graph in the browser. Point it at any public GitHub repository and it will fetch source files, parse imports to build a graph, request file-level AI insights, and expose a dashboard with charts and a file viewer.

**This project is intended as a portfolio backend+frontend demo** it shows backend services for crawling and analyzing code, background AI processing, and a React-based interactive visualization frontend. It supports only public GitHub repositories (no authentication flows or private repo access are implemented).

## Tech stack

- Backend: FastAPI, SQLAlchemy, Alembic
- AI: Groq (model reference: llama-3.3-70b) via the project's AI service wrapper
- Frontend: React, Vite, Canvas API (force-directed graph rendering)
- Utilities: Python tooling for parsing and repo fetching, simple SQLite support via SQLAlchemy

## Features

- Interactive dependency graph (force-directed) with pan / zoom / drag
- Per-file AI analysis: role classification, complexity estimate, short summary
- Language breakdown charts and simple metrics (line counts, import counts)
- File role classification and file source viewer

## Setup

Follow the backend and frontend instructions below. These steps assume a development machine with Python 3.10+ and Node.js installed.

### Backend

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

2. Copy and populate environment variables:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set GROQ_API_KEY (required). Optionally add GITHUB_TOKEN to increase GitHub rate limits.
```

3. Initialize the database and run migrations:

```bash
cd backend
alembic upgrade head
```

4. Run the development server:

```bash
uvicorn app.main:app --reload
```

Note: the backend enqueues background tasks to perform AI analysis and repository summarization. Large repositories may take time to finish processing.

### Frontend

1. Install dependencies and run the dev server:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

2. Open the frontend (Vite) server address (usually http://localhost:5173) and point the app at the backend API (default backend: http://localhost:8000). You can set `VITE_API_URL` in `frontend/.env` if your backend runs on a different host/port.

The frontend does not use any shared secret or API key. Browser code is public, so abuse control for this demo comes from backend rate limiting rather than a client-side credential.

## Environment variables

| Name | Required | Description |
|------|----------|-------------|
| `GROQ_API_KEY` | Yes | API key for the Groq LLM used for file and repo analysis. Without this the AI features will fail. |
| `VITE_API_URL` | No | Frontend-only backend base URL for local development. It is not an auth boundary. |
| `GITHUB_TOKEN` | No | Optional GitHub Personal Access Token — increases API rate limits when fetching repository trees and files. |
| `DATABASE_URL` | No | Database connection string. Defaults to a local SQLite file when not provided. Production deployments should point this to PostgreSQL because SQLite will not handle concurrent background writes well. 

## Limitations & Notes

- Only public GitHub repositories are supported. Private repositories are not supported by this demo.
- Public repository analysis is protected by server-side IP rate limiting, not by any frontend-exposed secret.
- AI requests are throttled and performed in background tasks — analysis of large repositories will take time and may be subject to rate limits.
- This repository intentionally does not implement authentication, onboarding flows, or team/collaboration features.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
