from __future__ import annotations

import json
import os
import sys
import time

import requests


EXAMPLES = (
    "pallets/flask",
    "tiangolo/fastapi",
    "expressjs/express",
    "vitejs/vite",
)
POLL_INTERVAL_SECONDS = 3
MAX_WAIT_SECONDS = 180


def main() -> None:
    api_url = os.environ.get("API_URL", "").strip().rstrip("/")
    if not api_url:
        raise SystemExit("Set API_URL to the backend base URL.")

    headers = {}
    api_key = os.environ.get("API_KEY", "").strip()
    if api_key:
        headers["X-API-Key"] = api_key

    with requests.Session() as session:
        for full_name in EXAMPLES:
            response = session.post(
                f"{api_url}/repos/analyze",
                json={"github_url": f"https://github.com/{full_name}"},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            repo = response.json()
            repo_id = repo["id"]
            deadline = time.monotonic() + MAX_WAIT_SECONDS

            while True:
                status_response = session.get(
                    f"{api_url}/repos/{repo_id}/status",
                    headers=headers,
                    timeout=30,
                )
                status_response.raise_for_status()
                status = status_response.json()
                if status["status"] == "ready":
                    break
                if status["status"] == "failed":
                    raise RuntimeError(
                        f"Analysis failed for {full_name}: {status.get('error') or 'Unknown error'}"
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for {full_name} to finish.")
                time.sleep(POLL_INTERVAL_SECONDS)

            result_response = session.get(
                f"{api_url}/repos/{repo_id}",
                headers=headers,
                timeout=30,
            )
            result_response.raise_for_status()
            print(f"{full_name}:")
            print(json.dumps(result_response.json(), indent=2))


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Seed request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
