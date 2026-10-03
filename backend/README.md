---
title: Codebase Visualizer API
emoji: 🗺️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# Codebase Visualizer API

FastAPI backend for the Codebase Visualizer. It fetches a public GitHub repository, parses its
imports into a file graph, and stores the results in Postgres. Analyses run in background tasks
and are coordinated through Redis.

Environment variables are documented in `.env.example`. Deployment steps are in the repository's
`DEPLOY.md`.
