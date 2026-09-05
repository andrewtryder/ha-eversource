# CI/CD notes

## Validation

The `Validate` workflow runs on pull requests, pushes to `main`, a daily schedule, and manual dispatch. It covers HACS, Hassfest, Ruff, and pytest (Python 3.14, ≥96% coverage). Those checks are the PR correctness gates.

## Live Eversource smoke

`Live Eversource smoke` fetches the public New Hampshire Rate R tariff pages on a schedule (and via `workflow_dispatch`). It is an **external dependency health check**, not a branch-protection or PR merge requirement. Eversource outages must not block ordinary code merges.

## Release Please authentication

Release Please opens version-bump PRs and creates GitHub releases/tags. PRs created with the default `GITHUB_TOKEN` often do not trigger the repository's full validation workflow chain the way a normal contributor PR does.

### Preferred: GitHub App

Create a dedicated GitHub App used only for Release Please.

Minimum repository permissions:

- **Contents:** Read and write
- **Pull requests:** Read and write

Do not grant administration, Actions write, Issues write, Packages write, or other unrelated scopes.

Install the App on `andrewtryder/ha-eversource`.

Add repository secrets (no real values in git):

| Secret | Purpose |
| --- | --- |
| `RELEASE_PLEASE_APP_ID` | Numeric GitHub App ID |
| `RELEASE_PLEASE_PRIVATE_KEY` | App private key PEM |

Also set repository variable:

| Variable | Value |
| --- | --- |
| `RELEASE_PLEASE_USE_APP` | `true` |

The App token step only runs when that variable is `true`, so missing App secrets cannot break the workflow. Until then, Release Please uses `RELEASE_PLEASE_TOKEN`.

### Fallback: fine-grained PAT

If an App is impractical, create a fine-grained personal access token with access to this repository and:

- **Contents:** Read and write
- **Pull requests:** Read and write

Store it as:

| Secret | Purpose |
| --- | --- |
| `RELEASE_PLEASE_TOKEN` | Fine-grained PAT used when the App secrets are unset |

Avoid classic PATs unless necessary. Never commit token values or print them in logs.

### Default behavior without setup

Until `RELEASE_PLEASE_USE_APP=true` (with App secrets) or `RELEASE_PLEASE_TOKEN` is configured, Release Please cannot authenticate. Configure the PAT first; enable the App later if desired.
