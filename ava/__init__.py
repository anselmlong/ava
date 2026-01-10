"""Compatibility package for `import ava`.

The codebase currently runs from the `src` package (e.g. `python -m src.main`).
Some tools/tests expect `import ava` to succeed, so this lightweight shim keeps
that import path working.
"""

from src import __version__

__all__ = ["__version__"]
