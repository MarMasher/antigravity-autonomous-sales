"""GitHub helper — creates repos and pushes files via the API."""
import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
API_BASE        = "https://api.github.com"

_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def create_repo(name: str, description: str = "", private: bool = False) -> dict:
    """Create a new GitHub repository. Returns repo info dict.
    On 403: fine-grained PAT may not have repo creation scope — silently continues.
    On 422: repo already exists — silently continues.
    """
    resp = requests.post(
        f"{API_BASE}/user/repos",
        headers=_HEADERS,
        json={"name": name, "description": description, "private": private, "auto_init": True},
        timeout=30,
    )
    if resp.status_code == 422:
        return {"html_url": get_repo_url(name), "note": "already exists"}
    if resp.status_code == 403:
        print(f"[GitHub] 403 on repo create — token may need 'repo' scope. Skipping create, will push files directly.")
        return {"html_url": get_repo_url(name), "note": "403 skipped"}
    resp.raise_for_status()
    return resp.json()


def push_file(repo_name: str, path: str, content: str, message: str = "feat: add file") -> dict:
    """Create or update a single file in the repo.
    Raises RuntimeError on 403/404 so the builder can skip gracefully.
    """
    url = f"{API_BASE}/repos/{GITHUB_USERNAME}/{repo_name}/contents/{path}"
    b64 = base64.b64encode(content.encode()).decode()
    sha = None
    check = requests.get(url, headers=_HEADERS, timeout=15)
    if check.status_code == 200:
        sha = check.json().get("sha")
    elif check.status_code in (403, 404):
        raise RuntimeError(f"GitHub {check.status_code} on {path} — check token permissions or create the repo manually at https://github.com/new (name: {repo_name})")
    payload = {"message": message, "content": b64}
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=_HEADERS, json=payload, timeout=30)
    if resp.status_code in (403, 404):
        raise RuntimeError(f"GitHub {resp.status_code} pushing {path}")
    resp.raise_for_status()
    return resp.json()



def get_repo_url(repo_name: str) -> str:
    return f"https://github.com/{GITHUB_USERNAME}/{repo_name}"


def enable_pages(repo_name: str) -> dict:
    """Enable GitHub Pages on main branch root — serves index.html directly."""
    resp = requests.post(
        f"{API_BASE}/repos/{GITHUB_USERNAME}/{repo_name}/pages",
        headers=_HEADERS,
        json={"source": {"branch": "main", "path": "/"}},
        timeout=30,
    )
    if resp.status_code in (409, 422):
        return {"note": "Pages already enabled"}
    if resp.status_code == 403:
        return {"note": "Token missing pages scope — enable Pages manually in repo Settings"}
    resp.raise_for_status()
    return resp.json()
