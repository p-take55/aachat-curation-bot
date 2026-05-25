"""Tool implementations for the curation agent.

These functions are exposed to the LLM but the JWT is loaded only inside the
host process — it never appears in tool arguments, return values, or prompts.
This is the "sidecar pattern" described in the aachat decision doc:
docs/decisions/D-20260512-discovery-curation-agent-write-path.md
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("AACHAT_API_URL", "http://localhost:3100").rstrip("/")
JWT_PATH = os.path.expandvars(
    os.environ.get("AACHAT_JWT_PATH", "$HOME/.aachat/curation-jwt")
)


def _load_jwt() -> str:
    path = Path(os.path.expanduser(JWT_PATH))
    if not path.exists():
        raise RuntimeError(
            f"JWT not found at {path}. Run `scripts/refresh-jwt.sh` to mint one. "
            "See knowledge/token-setup.md."
        )
    return path.read_text().strip()


def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    jwt = _load_jwt()
    r = requests.post(
        f"{API_URL}{endpoint}",
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if r.status_code >= 400:
        # Surface the structured error from aachat to the caller so the LLM
        # can decide what to do. JWT is NOT in the response so it is safe
        # to forward.
        try:
            return {"status": r.status_code, "error": r.json()}
        except ValueError:
            return {"status": r.status_code, "error": {"message": r.text}}
    return {"status": r.status_code, "data": r.json()}


def register_agent(
    github_repo: str,
    description_ja: str | None = None,
    description_en: str | None = None,
    skill_descriptions: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Register a GitHub repo as an agent in the aachat Discover catalog.

    The repo must be public and contain CLAUDE.md or identity.md at the root.

    - If the JWT owner matches the repo's GitHub login, the row is recorded
      with `origin='user_submit'`.
    - Otherwise it is recorded with `origin='curated'`.

    Child skills under `skills/` are auto-registered with the same `origin`.

    Curation descriptions (optional; this is the whole point of the curation
    agent — write the bilingual blurb the GitHub repo lacks):

    - `description_ja` / `description_en`: markdown blurb stored on the catalog
      row, separate from the GitHub repo description. Each is 1..=5000 chars
      after trim. On re-submit the server COALESCEs — a non-null value
      overwrites, null/omitted keeps the existing value (so you cannot clear a
      field back to empty once set).
    - `skill_descriptions`: per-child-skill bilingual blurbs in one round-trip.
      Keys are `skills/<dir>` paths; a key that doesn't match a skill the
      walker found in the repo is rejected with 400.
    """
    payload: dict[str, Any] = {"github_repo": github_repo}
    if description_ja is not None:
        payload["description_ja"] = description_ja
    if description_en is not None:
        payload["description_en"] = description_en
    if skill_descriptions:
        payload["skill_descriptions"] = skill_descriptions
    return _post("/v1/agents/discover", payload)


def register_skill(
    github_repo: str,
    skill_path: str,
    description_ja: str | None = None,
    description_en: str | None = None,
) -> dict[str, Any]:
    """Register a single skill (SKILL.md) under a repo to the catalog.

    `skill_path` must be a relative path. Use `"."` if the SKILL.md is at the
    repo root. The path may not contain `..`, leading `/`, `%`, null bytes,
    or `//`.

    This endpoint does not require a parent agent row — repos that are
    "skill-only" (no CLAUDE.md / identity.md) can still publish individual
    skills this way.

    `description_ja` / `description_en` behave exactly as in `register_agent`
    (optional, 1..=5000 chars, COALESCE on re-submit).
    """
    payload: dict[str, Any] = {"github_repo": github_repo, "skill_path": skill_path}
    if description_ja is not None:
        payload["description_ja"] = description_ja
    if description_en is not None:
        payload["description_en"] = description_en
    return _post("/v1/skills/discover", payload)
