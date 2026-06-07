"""Vercel deployment helper via REST API v9/v13."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")
API_BASE     = "https://api.vercel.com"
_HEADERS     = {"Authorization": f"Bearer {VERCEL_TOKEN}"}


def create_project(name: str, github_repo: str, github_username: str) -> dict:
    """
    Link a GitHub repo to a new Vercel project.
    github_repo: just the repo name (not full URL).
    """
    resp = requests.post(
        f"{API_BASE}/v9/projects",
        headers=_HEADERS,
        json={
            "name": name,
            "framework": "nextjs",
            "gitRepository": {
                "type": "github",
                "repo": f"{github_username}/{github_repo}",
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def trigger_deploy(project_name: str) -> dict:
    """Trigger a deployment from the latest commit."""
    resp = requests.post(
        f"{API_BASE}/v13/deployments",
        headers=_HEADERS,
        json={"name": project_name, "target": "production"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_deployment_url(deploy_id: str) -> str:
    """Poll until deployment is ready; return the live URL."""
    import time
    for _ in range(30):          # poll up to 5 min
        resp = requests.get(f"{API_BASE}/v13/deployments/{deploy_id}", headers=_HEADERS, timeout=20)
        data = resp.json()
        state = data.get("readyState") or data.get("state", "")
        if state in ("READY", "ready"):
            return "https://" + data["url"]
        if state in ("ERROR", "CANCELED"):
            raise RuntimeError(f"Vercel deploy failed: {state}")
        time.sleep(10)
    raise TimeoutError("Vercel deploy timed out after 5 min")
