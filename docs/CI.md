# CI, Coverage, and Badges

This repository uses GitHub Actions to run tests, perform a lightweight secret scan, and publish a coverage badge without any external services.

## What the workflow does

- Triggers on push and pull requests
- Sets up Python (3.10 and 3.11)
- Installs project and dev dependencies
- Runs pytest with coverage in offline mode (no live integrations)
- Runs a secret scan (`scripts/secret_scan.py`)
- Generates `coverage-badge.json` from `coverage.xml`
- Commits `coverage-badge.json` back to the `main` branch so Shields.io can render the badge

The workflow file lives at `.github/workflows/ci.yml`.

## Badges in README

- CI: shows whether the workflow is passing on the `main` branch
- Coverage: reads `coverage-badge.json` from the `main` branch via a Shields endpoint

If you later switch to `main`, update both the README badges and the workflow step that commits `coverage-badge.json`.

### Changing badges to track a different branch

If you temporarily want badges to track another branch (e.g., a long-lived feature branch), update:
1. README badges to reference that branch.
2. The commit condition in `.github/workflows/ci.yml` (e.g., `refs/heads/feature-x`).

## Local runs

You can run the same steps locally:

```powershell
# From repo root
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install pytest pytest-cov

# Run offline tests with coverage
$env:USE_REAL_TESTS="0"; pytest --cov=agent --cov=tests --cov-report=xml --cov-report=term-missing -q

# Generate badge JSON
python scripts/make_coverage_badge.py
```

This will produce `coverage.xml` and `coverage-badge.json` locally; the badge in README updates when CI pushes the JSON to the branch.

## Notes on live tests

Live integrations are gated by env flags and credentials and are disabled in CI. To run them locally, set the appropriate environment variables (e.g., `USE_REAL_TESTS=1` plus any backend credentials), but avoid committing secrets.

## Overriding `main` with `migration`

If you want the `main` branch to be replaced by the current `migration` branch:

- Preferred (safe) via PR:
  1. Open a Pull Request from `migration` → `main`.
  2. Resolve any branch protections and merge the PR (squash/merge is fine).
  3. Update README badges and the CI workflow to point to `main` (see steps above).

- Force update via the command line (use with care):

```powershell
# Ensure you have no uncommitted work
git fetch origin

# Reset your local main to migration
git checkout main
git reset --hard origin/migration

# Push the new main history
# If branch protection disallows force pushes, temporarily adjust settings or use a PR
git push origin main --force-with-lease
```

- After switching to `main`:
  - Update `.github/workflows/ci.yml` commit condition to `refs/heads/main`
  - Update README badges to reference `main`
  - Consider setting `main` as the default branch in GitHub Settings → Branches

## Troubleshooting

- If the coverage badge shows as "unknown": ensure `coverage-badge.json` exists on the branch and the Shields URL points to the correct branch.
- If CI cannot push the badge JSON: confirm the job runs on the target branch and branch protections allow workflow commits (or commit the badge into a `docs/` directory instead and allow updates there).
