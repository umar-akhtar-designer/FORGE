"""GitHub PR integration — push a FORGE-verified fix to a real repository.

Optional feature gated on ``GITHUB_TOKEN`` + ``GITHUB_REPO``. When a mission
commits real changes, FORGE can open a PR on GitHub containing exactly those
files (branch per mission, base = the repo's default branch), with a body that
reproduces the evidence trail. Uses only the REST API (no local git needed).

Everything is honest: the PR contains only changes the pipeline actually
committed (skill playbook or LLM-repair verified by the real validation suite).
"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path

import httpx

from .. import config, store
from .diff import apply_unified_diff
from .upload import extract_upload, register_repository

GH_API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(config.GITHUB_TOKEN and "/" in config.GITHUB_REPO)


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _raise(response: httpx.Response) -> None:
    try:
        body = response.json().get("message", response.text[:200])
    except ValueError:
        body = response.text[:200]
    raise GitHubError(f"GitHub API {response.status_code}: {body}")


_REPO_URL_RE = re.compile(r"^(?:https?://github.com/|git@github.com:|([^/@]+)/)")
_BARE_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")


def parse_repo_url(url: str) -> tuple[str, str, str | None]:
    """Normalize a GitHub URL/shorthand into (owner, repo, branch)."""
    url = url.strip().rstrip("/")
    if url.startswith("git@github.com:"):
        rest = url.split(":", 1)[1]
    elif "github.com/" in url:
        rest = url.split("github.com/", 1)[1]
    elif "/" in url and not url.startswith(("http", "git@")):
        rest = url
    else:
        raise ValueError(f"Not a GitHub repository reference: {url!r}")
    rest = rest.removeprefix("www.")
    parts = rest.split("/")
    if len(parts) < 2:
        raise ValueError(f"Not a GitHub repository reference: {url!r}")
    owner, repo = parts[0], parts[1]
    branch = None
    if repo.endswith(".git"):
        repo = repo[:-4]
    if len(parts) >= 3 and parts[2] == "tree" and len(parts) >= 4:
        branch = parts[3]
    if not owner or not repo or not _BARE_RE.match(f"{owner}/{repo}"):
        raise ValueError(f"Not a GitHub repository reference: {url!r}")
    return owner, repo, branch


def connect_repository(url: str) -> dict:
    """Clone a GitHub repository (by URL) into FORGE and register it.

    Works for any public repository; a configured ``GITHUB_TOKEN`` is used when
    present so private repositories can be connected too. The result feeds the
    normal mission → PR pipeline. No git binary is required — codeload zip.
    """
    owner, repo, branch = parse_repo_url(url)
    branch = branch or config.GITHUB_DEFAULT_BRANCH or "main"
    zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    headers = {"User-Agent": "forge-control-plane"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    try:
        resp = httpx.get(zip_url, headers=headers, follow_redirects=True, timeout=120)
    except httpx.HTTPError as exc:
        raise GitHubError(f"Failed to reach codeload.github.com: {exc}") from exc
    if resp.status_code != 200:
        raise GitHubError(f"GitHub codeload {resp.status_code}: {resp.text[:200]}")
    try:
        root, name = extract_upload(resp.content, f"{owner}-{repo}")
    except ValueError as exc:  # noqa: BLE001
        raise GitHubError(f"Archive rejected: {exc}") from exc
    index = register_repository(root, name)
    index["source"] = {
        "owner": owner, "repo": repo, "branch": branch,
        "html_url": f"https://github.com/{owner}/{repo}",
        "zip_url": zip_url,
    }
    return index


def _final_content(mission_id: str, rel: str, pristine: Path) -> str:
    """The committed file content: workspace copy if still present, else pristine+diff."""
    workspace = config.WORKSPACES_DIR / mission_id / "repo"
    w = workspace / rel
    if w.is_file():
        try:
            return w.read_text(encoding="utf-8")
        except OSError:
            pass
    base = pristine / rel
    before = base.read_text(encoding="utf-8") if base.is_file() else ""
    diff = next((c.diff for c in store.get_code_changes(mission_id) if c.path == rel), "")
    return apply_unified_diff(before, diff) if diff else before


def create_pr(mission_id: str) -> dict:
    """Open a PR with the mission's committed changes. Returns PR metadata."""
    owner, repo = config.GITHUB_REPO.split("/", 1)
    changes = store.get_code_changes(mission_id)
    if not changes:
        raise GitHubError("No committed changes to push for this mission.")
    mission = store.get_mission(mission_id)
    if mission is None:
        raise GitHubError("Mission not found.")

    head = f"forge-{mission_id.replace('mission-', '')}-{uuid.uuid4().hex[:4]}"
    with httpx.Client(timeout=30) as client:
        base = config.GITHUB_DEFAULT_BRANCH
        r = client.get(f"{GH_API}/repos/{owner}/{repo}", headers=_headers())
        if r.status_code == 200:
            base = r.json().get("default_branch", base)
        else:
            _raise(r)

        r = client.get(f"{GH_API}/repos/{owner}/{repo}/git/refs/heads/{base}", headers=_headers())
        if r.status_code != 200:
            _raise(r)
        sha = r.json()["object"]["sha"]

        r = client.post(f"{GH_API}/repos/{owner}/{repo}/git/refs", headers=_headers(),
                        json={"ref": f"refs/heads/{head}", "sha": sha})
        if r.status_code not in (200, 201) and "already exists" not in r.text.lower():
            _raise(r)

        pristine = Path("")
        for idx in store.list_repository_indexes():
            if idx.name == mission.repository:
                pristine = Path(idx.path)
                break
        changed_files = []
        for c in changes:
            content = _final_content(mission_id, c.path, pristine)
            r = client.put(f"{GH_API}/repos/{owner}/{repo}/contents/{c.path}", headers=_headers(),
                           json={"message": f"FORGE: {mission.title}",
                                 "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                                 "branch": head})
            if r.status_code not in (200, 201):
                _raise(r)
            changed_files.append(c.path)

        root_cause = ""
        for f in store.get_findings(mission_id):
            if f.agent == "debugger":
                root_cause = f"{f.title} — {f.detail} ({f.file}{f.line or ''})"
                break

        summary = mission.summary or ""
        body = (
            f"## FORGE engineering mission\n\n"
            f"**Mission:** {mission.title}\n\n"
            f"> {mission.mission_text or '(no mission text)'}\n\n"
            + (f"**Root cause:** {root_cause}\n\n" if root_cause else "")
            + f"**Files changed ({len(changed_files)}):** {', '.join(changed_files)}\n\n"
            + f"**Release gate:** {summary}\n\n"
            + "### Evidence\n\n"
            + "- Every change was verified by the real validation suite before being committed.\n"
            + "- Findings, tests, security scan and review are all recorded deterministically from execution.\n"
        )

        r = client.post(f"{GH_API}/repos/{owner}/{repo}/pulls", headers=_headers(),
                        json={"title": f"FORGE: {mission.title}", "head": head, "base": base, "body": body})
        if r.status_code not in (200, 201):
            _raise(r)
        pr = r.json()

    store.add_audit(mission_id, "github", "pull-request", f"PR opened: #{pr.get('number')} {pr.get('html_url')}")
    return {"number": pr.get("number"), "url": pr.get("html_url"), "branch": head}