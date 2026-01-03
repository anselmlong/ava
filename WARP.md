# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.
``

## Repository overview

- Project name: `ava`
- Description from `README.md`: "Your AI Assistant".
- As of now, the repository only contains `README.md` and no application code or tooling configuration files.

## Build, test, and lint commands

No build, test, or lint tooling is currently defined in this repository (there is no `package.json`, `pyproject.toml`, `Makefile`, or similar).

When such tooling is added, prefer to:
- Use the scripts or tasks defined in the primary project configuration (for example `package.json` scripts, `pyproject.toml` tool sections, or a `Makefile`/task runner file).
- Run tests and linters via those project-specific commands rather than invoking tools directly, so that configuration is picked up correctly.

If you are unsure which commands to use, first inspect root-level config files (e.g. `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`) and any `README` or docs that may be added later, then update this `WARP.md` accordingly.

## Architecture and project structure

There is no committed source code yet, so there is no architecture or module structure to document at this time.

Once application code is added, future edits to this file should document:
- The main entry point(s) for the application (e.g. CLI, server, or UI layer).
- How major modules are organized (domains, features, services, shared utilities) and how they depend on each other.
- Any non-obvious conventions (for example, where to put integration tests vs. unit tests, or how configuration and secrets are loaded).
