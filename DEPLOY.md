# Deployment

- **Frontend:** Vercel, root directory `frontend`.
- **Backend:** Hugging Face Space (Docker SDK), built from `backend/Dockerfile`.
- **Database:** Neon Postgres. **Cache and rate-limit state:** Upstash Redis.

The backend must run as a single persistent process. Analyses run as background tasks and startup
resumes unfinished ones, so do not add workers or split it into serverless functions.

Migrations run automatically before the app starts (`backend/entrypoint.sh`). If a migration fails,
the container exits and the Space shows as stopped.

Placeholders below look like `<...>`. Replace them with your own values in the dashboards.
Never commit real values to the repository.

---

## a. Space environment variables

Set these in **Space → Settings → Variables and secrets**. Use **Secrets** for anything marked
secret. Use **Variables** for the rest.

| Name | Type | Value |
| --- | --- | --- |
| `DATABASE_URL` | Secret | Neon connection string (see b1) |
| `REDIS_URL` | Secret | Upstash `rediss://` URL (see b2) |
| `API_KEY` | Secret | Generated key (see b4). Must equal `VITE_API_KEY` on Vercel |
| `GITHUB_TOKEN` | Secret | Fine-grained read-only token (see b3). Required in production |
| `GROQ_API_KEY` | Secret | Optional. Only needed for AI summaries |
| `APP_ENV` | Variable | `production` |
| `CORS_ORIGINS` | Variable | JSON array with your exact Vercel URL, e.g. `["https://<project>.vercel.app"]`. No trailing slash, no `*`. Use JSON, not comma-separated: a plain comma list makes the app fail at startup |
| `TRUST_PROXY_HEADERS` | Variable | `True` (the Space sits behind a proxy; without this, every user shares one rate-limit bucket) |
| `TRUSTED_PROXY_COUNT` | Variable | Hop count from section f. Start with `1` and verify |
| `LOG_LEVEL` | Variable | `INFO`. Set to `DEBUG` only while doing section f, then set it back |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Variable | Optional. Default `20` |
| `MAX_REPO_FILES` | Variable | Optional. Default `300` |
| `MAX_CONCURRENT_REPO_ANALYSES` | Variable | Optional. Default `5` |

The backend refuses to start in production without `API_KEY` and `GITHUB_TOKEN`, and it refuses
SQLite. A missing `REDIS_URL` will also fail readiness.

All variable names and defaults are documented in `backend/.env.example`.

---

## b. Where each value comes from

**b1. `DATABASE_URL` (Neon)**
1. Create a project at neon.tech and copy the connection string from the dashboard.
2. It looks like `postgresql://<user>:<password>@<host>/<db>?sslmode=require`.
3. Make sure `sslmode=require` is present. The app also accepts `postgres://` and rewrites it.

**b2. `REDIS_URL` (Upstash)**
1. Create a Redis database at upstash.com. Keep TLS enabled.
2. Copy the **`rediss://`** URL (double `s`) from the database details page.

**b3. `GITHUB_TOKEN`**
1. GitHub → Settings → Developer settings → Fine-grained personal access tokens → Generate new token.
2. Resource owner: your account. Repository access: **Public repositories (read-only)**.
   No additional permissions are needed for reading public repos.
3. Set an expiry date and copy the token once.

**b4. `API_KEY`**
Generate it locally:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the same value in the Space (`API_KEY`) and in Vercel (`VITE_API_KEY`).

---

## c. Pushing only `backend/` to the Space

A Space is its own git repository, and its root must contain the Dockerfile and README. The
commands below publish just the `backend/` folder of this repo.

One-time setup: create a new Space at huggingface.co/new-space, choose **Docker** as the SDK and
**Blank** as the template. Then create a Hugging Face access token with write permission. Git will
ask for it as the password (username is your HF username).

```sh
# from the repo root
git subtree split --prefix backend -b hf-space
git push https://huggingface.co/spaces/<HF_USER>/<SPACE_NAME> hf-space:main --force
git branch -D hf-space   # optional cleanup
```

Every deploy repeats the same three commands.

Tradeoffs:
- `--force` replaces the Space's history with the split history. That is fine because the Space holds only the backend.
- Splitting walks the whole repo history, so it gets slower as the history grows. Splitting once per deploy is fine at this size.
- The Space rebuilds on every push, and the build takes a few minutes.

---

## d. Vercel (frontend)

1. Import the GitHub repo in Vercel.
2. **Root Directory:** `frontend`. **Framework Preset:** Vite. Build command `npm run build`, output `dist`.
3. Environment variables (Production):
   - `VITE_API_URL` = the Space's direct URL, `https://<HF_USER>-<SPACE_NAME>.hf.space` (no trailing slash)
   - `VITE_API_KEY` = same value as the Space's `API_KEY`
4. Deploy. Then set `CORS_ORIGINS` on the Space to the exact deployed origin and let the Space restart.

**`VITE_*` values are public.** Vite inlines them into the JavaScript the browser downloads.
Anyone can read `VITE_API_KEY` from the bundle. The key only deters casual abuse. Real protection
comes from rate limits. Never put `GITHUB_TOKEN`, `GROQ_API_KEY`, or database credentials in a
`VITE_` variable.

If `VITE_API_URL` is missing in a production build, the app shows "API URL not configured".

---

## e. Post-deploy smoke test

Replace `<SPACE_URL>` with `https://<HF_USER>-<SPACE_NAME>.hf.space`.

```sh
# 1. Process is up
curl -s <SPACE_URL>/health
# expect: {"status":"ok","version":"0.1.0","env":"production"}

# 2. Database and Redis are reachable
curl -s <SPACE_URL>/health/ready
# expect HTTP 200 and: {"status":"ok","checks":{"database":"ok","redis":"ok"}}
# 503 means one of the two checks failed. The body says which one.

# 3. End to end: analyze a small public repo through the UI
#    Open the Vercel site, paste a small public GitHub repo URL, and confirm the graph loads.
```

**Rate limit check** (default is 20 analyze requests per minute per IP). Run from your own machine:

```sh
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST <SPACE_URL>/repos/analyze \
    -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
    -d '{"github_url":"https://github.com/<owner>/<small-repo>"}'
done
```

You should see `429` once the limit is exceeded (usually after 20 requests). Some early requests
start real analyses, so use a small repo.

Then repeat a single request from a different network, such as a phone hotspot. It should not
return `429` if the first network was already limited. This only works once `TRUSTED_PROXY_COUNT`
is correct (section f). If both networks share a bucket, the hop count is wrong.

---

## f. Determining `TRUSTED_PROXY_COUNT`

The backend takes the client IP from `X-Forwarded-For`, counting `TRUSTED_PROXY_COUNT` entries
from the right. The right number is the number of proxies that append to the header.

1. Find your public IP from a site such as `https://api.ipify.org`.
2. In the Space variables, set `LOG_LEVEL=DEBUG` and restart the Space.
3. Send one request from your machine to a route that resolves the client IP, the analyze endpoint
   (`/health` and `/health/ready` do not log it):
   `curl -s -X POST <SPACE_URL>/repos/analyze -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"github_url":"https://github.com/<owner>/<small-repo>"}'`
4. Open **Space → Logs** and find the line starting with `client.host=... x-forwarded-for=...`.
   The debug log prints the raw header, so it may include IPs from other clients. Treat the logs as private.
5. Split the header by commas. Count from the right until you reach the entry that equals your
   public IP. That position is `TRUSTED_PROXY_COUNT`.
   - If your IP is the last entry, the count is `1`.
   - If it is second from the right, the count is `2`.
6. Set `TRUSTED_PROXY_COUNT` to that number, set `LOG_LEVEL=INFO`, and restart.
7. Repeat the rate-limit test from section e from two networks.

If no entry matches your IP, the header is not what you expect. Keep `TRUSTED_PROXY_COUNT`
conservative and check the logs again before counting on rate limits.

With `TRUST_PROXY_HEADERS=True` and `TRUSTED_PROXY_COUNT=0`, the app trusts the leftmost,
client-supplied entry. Clients can spoof that, so do not leave the count at `0` in production.

---

## g. Known limits

- **Cold starts.** Free Spaces sleep when idle. The first request after sleep waits for the
  container to restart, which includes running migrations.
- **Persistence.** Analyses in progress are resumed on startup from the database. Long jobs can still
  be interrupted by a Space restart or a sleep, and they will be retried.
- **Single worker.** The app supports one uvicorn worker only. Throughput is limited by the free CPU tier.
- **Database quota.** Neon free tiers have storage, compute-hour, and idle-suspend limits. The first
  request after suspend is slower.
- **Redis quota.** Upstash free tiers have monthly command and storage caps. Rate limiting and repo
  locks are stored in Redis, so exhausting the quota makes `/health/ready` fail.
- **GitHub API.** Without a token, GitHub allows 60 requests per hour per IP. The token raises it to
  5000 per hour. Large repos can still hit secondary limits.
- **Free-tier terms.** Quotas and sleep behavior change. Check the current pricing pages of Hugging
  Face, Neon, Upstash, and Vercel before relying on them.
