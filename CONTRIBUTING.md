# Contributing to Eversource Rates

## Local setup

Create a virtual environment, then install both dependency sets and hooks:

```shell
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements_test.txt
.venv/bin/pre-commit install
```

Run the complete local gate before opening a pull request:

```shell
.venv/bin/ruff check .
.venv/bin/ruff format --check .
PYTHONPATH=. .venv/bin/pytest
.venv/bin/pre-commit run --all-files
```

Hassfest can also be run with `docker run --rm -v "$(pwd)/custom_components:/github/workspace/custom_components" ghcr.io/home-assistant/hassfest`.

## Pull requests and releases

PRs are squash-only. Their title becomes the commit title on `main`, so it must follow Conventional Commits and begin its subject with lowercase text. Release Please uses that title to create release PRs and changelog entries.

Allowed types are `feat`, `fix`, `deps`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`. Examples: `feat(sensor): add total electricity rate`, `fix(parser): normalize a rider`, and `docs: clarify HACS installation`. `feat` produces a minor release; `fix` produces a patch release; `feat!` and `fix!` signal breaking changes. Intermediate branch commits need not be conventional.

Do not manually change the integration version or `CHANGELOG.md`; Release Please owns both. Do not merge a Release Please PR automatically.

## Privacy and scope

The integration domain is `eversource_rates` at `custom_components/eversource_rates/`. Do not commit Eversource account data, bills, addresses, logged-in cookies, tokens, browser profiles, or raw authenticated captures. Public tariff fixtures must remain sanitized. Current production scope is NH Residential Rate R only.
