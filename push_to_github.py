"""
GraphMind GitHub Push Script — Fixed Version
Uses GitHub REST API to push all local files directly.
"""

import base64
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

OWNER  = "lazee01"
REPO   = "graphmind"
BRANCH = "main"
BASE   = Path(r"C:\Users\RYZEN\PycharmProjects\graphmind")

FILES = [
    # Backend app
    (BASE / "backend/app/__init__.py",            "backend/app/__init__.py"),
    (BASE / "backend/app/providers.py",           "backend/app/providers.py"),
    (BASE / "backend/app/agents.py",              "backend/app/agents.py"),
    (BASE / "backend/app/core.py",                "backend/app/core.py"),
    (BASE / "backend/app/auth.py",                "backend/app/auth.py"),
    (BASE / "backend/app/main.py",                "backend/app/main.py"),
    # Backend config
    (BASE / "backend/requirements.txt",           "backend/requirements.txt"),
    (BASE / "backend/requirements-optional.txt",  "backend/requirements-optional.txt"),
    (BASE / "backend/.env.example",               "backend/.env.example"),
    (BASE / "backend/Dockerfile",                 "backend/Dockerfile"),
    # Tests
    (BASE / "backend/tests/__init__.py",          "backend/tests/__init__.py"),
    (BASE / "backend/tests/test_core.py",         "backend/tests/test_core.py"),
    (BASE / "backend/tests/test_api.py",          "backend/tests/test_api.py"),
    # Frontend hook
    (BASE / "src/hooks/useGraphMind.ts",          "src/hooks/useGraphMind.ts"),
    # Root config
    (BASE / "docker-compose.yml",                 "docker-compose.yml"),
    (BASE / ".gitignore",                         ".gitignore"),
]

# Auto-include any extra frontend files if they exist
EXTRA = [
    "src/GraphMindApp.tsx",
    "src/main.tsx",
    "src/styles.css",
    "src/vite-env.d.ts",
    "src/components/AnswerPanel.tsx",
    "src/components/EvidenceCard.tsx",
    "src/components/GraphPanel.tsx",
    "src/components/DocumentList.tsx",
    "src/components/PDFUploader.tsx",
    "src/components/LoginPage.tsx",
    "src/components/AuthGuard.tsx",
    "src/lib/firebase.ts",
    "public/graphmind-icon.svg",
    "index.html",
    "package.json",
    "tsconfig.json",
    "vite.config.js",
]
for rp in EXTRA:
    lp = BASE / rp
    if lp.exists():
        FILES.append((lp, rp))


def gh(token, method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "graphmind-push",
    })
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read()), None
    except HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()
        except Exception:
            pass
        return None, f"HTTP {e.code}: {err_body[:200]}"


def push_file(token, local_path, repo_path):
    if not local_path.exists():
        return "SKIP", f"{repo_path} — file not found locally"

    content = base64.b64encode(local_path.read_bytes()).decode()

    # Get existing SHA if file already exists in repo
    existing, _ = gh(token, "GET", f"/repos/{OWNER}/{REPO}/contents/{repo_path}?ref={BRANCH}")
    sha = existing["sha"] if existing and isinstance(existing, dict) and "sha" in existing else None

    body = {
        "message": f"build: add/update {repo_path}",
        "content": content,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    result, err = gh(token, "PUT", f"/repos/{OWNER}/{REPO}/contents/{repo_path}", body)
    if err:
        return "FAIL", f"{repo_path} — {err}"
    return "OK", repo_path


def main():
    token = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not token:
        print("Usage: python push_to_github.py <TOKEN>")
        sys.exit(1)

    print(f"\n🚀  Pushing GraphMind → github.com/{OWNER}/{REPO}\n")
    ok = fail = skip = 0

    for i, (local_path, repo_path) in enumerate(FILES, 1):
        print(f"  [{i:02d}/{len(FILES)}] {repo_path:<52}", end=" ", flush=True)
        status, msg = push_file(token, local_path, repo_path)
        if status == "OK":
            print("✅")
            ok += 1
        elif status == "SKIP":
            print(f"⏭  {msg}")
            skip += 1
        else:
            print(f"❌  {msg}")
            fail += 1

    print(f"\n{'='*60}")
    print(f"  ✅ Pushed : {ok}   ⏭ Skipped : {skip}   ❌ Failed : {fail}")
    print(f"  🔗 https://github.com/{OWNER}/{REPO}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
