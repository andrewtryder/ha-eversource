# Contributing to Eversource Rates

## Prerequisites

Development expects:

- Python 3.14
- Git
- A Python virtual environment
- Repository development and test dependencies

Docker and a devcontainer are intentionally not required for this project.

## Local setup

Create and activate a virtual environment, upgrade pip, and install dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements_test.txt
```

*(On Windows, activate with `.venv\Scripts\activate`.)*

Optionally install pre-commit git hooks:

```bash
pre-commit install
```

## Validation

Run the validation suite used by CI before opening a pull request:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest
```

### Purpose of each check

- **Ruff linting (`ruff check .`)**: Checks code style, imports, and lint rules defined in `pyproject.toml`.
- **Ruff format check (`ruff format --check .`)**: Verifies code formatting conforms to repo conventions without altering files.
- **Unit and integration tests (`PYTHONPATH=. pytest`)**: Executes the test suite against local fixtures and mock Home Assistant components.
- **Coverage enforcement**: `pyproject.toml` configures `--cov-fail-under=96`, failing the test run if total line coverage drops below 96%.

If you have pre-commit installed, you can also run the full local hook suite:

```bash
pre-commit run --all-files
```

### Formatting and auto-fixing

Before running validation, you can automatically fix format and lint issues:

```bash
ruff check . --fix
ruff format .
```

Always rerun the validation commands above after applying automatic fixes.

### Home Assistant CI checks

In addition to Python tests and linting, GitHub Actions CI runs:

- **HACS validation**: Validates integration structure and metadata against HACS rules.
- **Home Assistant `hassfest`**: Validates manifest, services, and integration structure.

Contributors generally do not need to run these checks locally unless desired.

## Test organization

- **Directory**: Test files reside under `tests/`.
- **Fixtures**: Sanitized public-page HTML snapshots are stored in `tests/fixtures/`.
- **Offline testing**: Parser behavior should be tested against fixture snapshots. Tests must remain deterministic and must not make live network requests to Eversource.
- **Live testing**: Manual verification against current live Eversource tariff pages is available via `tools/fetch_eversource_rates.py`.
- **Regression coverage**: Any changed parser or integration behavior must include focused regression tests.

## Parser development guidance

Territory-specific parsers remain intentionally separated into distinct modules (`parsers/nh.py`, `parsers/ct.py`, `parsers/ma.py`). Do not unify them into a single generic parser.

- **Fail-closed**: Parsing must raise an error and fail closed when expected table structure, headers, or required data components are missing.
- **Exact math**: Use `Decimal` for all rates, charges, and sums. Never use binary floats for currency or tariff rates.
- **Semantic matching**: Locate table cells and data by semantic labels, headings, and row titles rather than fragile positional indexes or CSS path selectors.
- **Fixtures**: When updating parser logic to reflect upstream Eversource website changes, update or add sanitized fixtures and matching regression tests.

## Pull requests and releases

PRs are squash-only. The PR title becomes the commit title on `main`, so it must follow Conventional Commits and begin its subject with lowercase text (e.g. `fix(parser): handle new rider heading`). Release Please uses that title to generate release notes, version bumps, and `CHANGELOG.md`.

Allowed commit types: `feat`, `fix`, `deps`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`. `feat` produces a minor release; `fix` produces a patch release; `feat!` or `fix!` signals a breaking change.

Do not manually edit version numbers or `CHANGELOG.md`; Release Please manages both. Never manually tag or merge a Release Please PR.

## Privacy and scope

The integration domain is `eversource_rates` at `custom_components/eversource_rates/`. Never commit Eversource account numbers, bills, street addresses, credentials, login cookies, session tokens, browser profiles, or unredacted raw captures. All tariff fixtures must contain only public rate information and remain fully sanitized.
