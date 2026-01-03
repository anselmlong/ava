"""Command-line entrypoint for Ava.

For now this just loads configuration and prints a simple message so you can
validate that the package is wired correctly. It will later be extended to run
Telegram webhook handling and the LangGraph agent.
"""

from __future__ import annotations

from .config import load_config


def main() -> None:
    config = load_config()
    print(f"Ava is starting in {config.env!r} environment.")


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()
