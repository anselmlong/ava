"""Main entry point for Ava bot."""

import sys
from pathlib import Path

# Allow running via `python src/main.py` without installing the package.
# When executed as a script, Python sets sys.path to `.../ava/src`, which
# breaks `import src.*` (it looks for `src/src`). Add the repo root instead.
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.bot import run_bot


def main() -> None:
    """Main entry point."""
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
