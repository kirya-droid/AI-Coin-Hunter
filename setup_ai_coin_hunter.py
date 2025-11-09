#!/usr/bin/env python3
"""Legacy scaffolding entry point for AI Coin Hunter.

This helper previously bootstrapped a bare-bones project layout with
hard-coded prompts (including an outdated ``gpt-4o-mini`` model
reference). The runtime has since moved to ``src/llm/explain.py`` and the
configurable ``LLMCfg`` pipeline, so keeping the generator around was
causing confusion.

Running the script now just prints guidance and exits with a non-zero
code so automation can fail fast instead of creating stale files.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_HINT = Path(__file__).resolve().parent


def main() -> int:
    message = (
        "setup_ai_coin_hunter.py is deprecated.\n"
        "Use the checked-in sources (see src/llm/explain.py for the current "
        "LLM integration) instead of generating an outdated scaffold.\n"
        f"Repository root: {ROOT_HINT}\n"
    )
    sys.stderr.write(message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
