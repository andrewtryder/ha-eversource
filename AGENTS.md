# Repository instructions

- Keep the integration domain and path as `eversource_rates` / `custom_components/eversource_rates`.
- Run `ruff check .`, `ruff format --check .`, `PYTHONPATH=. pytest`, and `pre-commit run --all-files`; coverage must remain at least 96%.
- PR titles must be lowercase Conventional Commits. The repository is squash-only, and Release Please owns versions and `CHANGELOG.md`.
- Never manually tag or merge a Release Please PR.
- Never commit Eversource authentication data, account data, browser profiles, or unsanitized page captures.
