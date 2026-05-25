"""Minimal CLI: register a single agent or skill from the command line.

This is the "manual" entry point — useful for testing the JWT setup, for
one-off registrations, and as a target for cron jobs. The LLM-driven flow
lives in `agent.py` (not yet implemented; see README).
"""

from __future__ import annotations

import argparse
import json
import sys

from .tools import register_agent, register_skill


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="curation-bot",
        description="Register an agent or skill repo to the aachat Discover catalog.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    agent = sub.add_parser("register-agent", help="Register a GitHub repo as an agent.")
    agent.add_argument("github_repo", help='e.g. "obra/superpowers"')
    agent.add_argument("--description-ja", help="Japanese curation blurb (markdown).")
    agent.add_argument("--description-en", help="English curation blurb (markdown).")
    agent.add_argument(
        "--skill-descriptions",
        metavar="JSON",
        help='Per-skill blurbs, e.g. \'{"skills/foo": {"description_ja": "…", "description_en": "…"}}\'',
    )

    skill = sub.add_parser("register-skill", help="Register a single SKILL.md as a skill.")
    skill.add_argument("github_repo")
    skill.add_argument("skill_path", help='e.g. "skills/brainstorming" or "." for root')
    skill.add_argument("--description-ja", help="Japanese curation blurb (markdown).")
    skill.add_argument("--description-en", help="English curation blurb (markdown).")

    args = parser.parse_args(argv)

    if args.cmd == "register-agent":
        skill_descriptions = (
            json.loads(args.skill_descriptions) if args.skill_descriptions else None
        )
        result = register_agent(
            args.github_repo,
            description_ja=args.description_ja,
            description_en=args.description_en,
            skill_descriptions=skill_descriptions,
        )
    elif args.cmd == "register-skill":
        result = register_skill(
            args.github_repo,
            args.skill_path,
            description_ja=args.description_ja,
            description_en=args.description_en,
        )
    else:
        parser.error(f"unknown command: {args.cmd}")
        return 2

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status", 0) < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
