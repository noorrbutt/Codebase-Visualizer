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

## Pruning old repository analyses

Run the pruning script from the backend directory after configuring its database environment:

```bash
python scripts/prune_repos.py --dry-run
python scripts/prune_repos.py --days 30
```

The default retention period is 30 days. Only `ready` and `failed` repositories with an
`updated_at` older than the cutoff are eligible; analyses with `parsing` status and rows with no
`updated_at` are never deleted. Dry-run reports the matching repository, file-node, and edge counts
without changing data.
