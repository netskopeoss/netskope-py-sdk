# Release netskope-py-sdk

You are performing a full release of the `netskope-py-sdk` package: commit + tag on GitHub, PyPI publish, and the GitHub Release. Everything after the tag push is done by `.github/workflows/release.yml`.

## Inputs

Do not ask the user for:
1. **Version bump type**: patch (1.2.0 → 1.2.1), minor (1.2.0 → 1.3.0), or major (1.2.0 → 2.0.0). Default: patch. If the user does not specify, assume a patch bump.
2. **Changelog entries**: the `[Unreleased]` section of CHANGELOG.md should already hold them, since every PR adds its own. Check `git log v<last>..HEAD` for anything missing and add it before releasing.

## Steps

### 1. Determine the new version
- Read the current version from `pyproject.toml` (field `version`)
- Compute the new version based on the bump type
- Find the previous release tag (`git tag --list | sort -V | tail`) and review `git log <last-tag>..HEAD` to build the changelog bullets

### 2. Update the version everywhere, then refresh the lockfile
The version is a literal in two files that `tests/unit/test_version.py` asserts agree, plus the docs page. `_version.__version__` also builds the `User-Agent` the SDK sends, so a stale literal misreports the SDK to the API.
- `pyproject.toml` → `version = "X.Y.Z"`, then run `uv lock`: `uv.lock` records the project's own version, and `uv lock --check` / `uv sync --locked` fail until it is refreshed
- `src/netskope/_version.py` → `__version__ = "X.Y.Z"`
- `docs/index.html` → FOUR spots, all currently reading `1.2.0`: the nav badge (line ~56, `<span ...>v1.2.0</span>`), the `print(netskope.__version__)` sample output (line ~192), the `client.version` sample output (line ~424) and the footer (line ~1918, `netskope-py-sdk v1.2.0`). Locate them with `grep -n '1\.2\.0' docs/index.html` against the version being replaced, and re-run that grep with the old version afterwards to confirm nothing was missed.
- Also validate that the rest of `docs/index.html` and the README don't need updates for this release's changes (new resources, changed signatures, new models). If they do, update them.

### 3. Drop the unpublished-development notices
`1.2.0.dev0` was never published, and the README and CHANGELOG say so in prose. The first release that actually ships must remove that wording, or the published docs describe themselves as unpublished.
```bash
grep -rn 'unpublished\|\.dev0' README.md CHANGELOG.md docs/
```
- README.md: the "Typed CLI integration (development)" section opens with "The unpublished `1.2.0.dev0` development version adds …". Rewrite it for the released version.
- CHANGELOG.md: the `[Unreleased]` preamble names `1.2.0.dev0` as an unpublished development version. That paragraph goes with the section when it is rotated in step 4.
- Skip this step entirely once those greps come back empty.

### 4. Update CHANGELOG.md
The file follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) throughout.
- Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and insert a fresh, empty `## [Unreleased]` above it.
- Entries sit under `### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed` and `### Security`, in that order, one or two sentences each on one unwrapped line; drop empty subsections. A release that changes an existing contract opens with `### Breaking`, listing each change, so the size of the version bump can be read off the changelog.
- Update the reference links at the bottom of the file: point `[Unreleased]` at `compare/vX.Y.Z...HEAD` and add `[X.Y.Z]: https://github.com/netskopeoss/netskope-py-sdk/compare/v<previous>...vX.Y.Z`. The file carries no link block yet, so the first release that goes through this runbook adds one:
```markdown
[Unreleased]: https://github.com/netskopeoss/netskope-py-sdk/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/netskopeoss/netskope-py-sdk/compare/v<previous>...vX.Y.Z
```
- `release.yml` reads the section back out with `sed -n '/^## \[X\.Y\.Z\]/,/^## \[/p'` to write the GitHub Release notes, so the heading must match `## [X.Y.Z] - YYYY-MM-DD` exactly.

### 5. Lint, format, type-check, test
```bash
uv run ruff check . --fix
uv run ruff format .
uv run ty check
uv run pytest
```
- If there are lint errors that can't be auto-fixed, stop and report them.
- ty must report 0 diagnostics and ALL tests must pass before continuing. If not, stop and report the issue — fix before continuing. `tests/unit/test_version.py` is the one that catches a half-finished step 2.

### 6. Commit, push and tag
```bash
git add pyproject.toml uv.lock src/netskope/_version.py CHANGELOG.md README.md docs/index.html
# Also add any other files modified in this session
git commit -m "Release vX.Y.Z - <short summary>"
git push origin main

# Annotated tag, pushed to GitHub. Pushing it starts the publish workflow.
git tag -a vX.Y.Z -m "vX.Y.Z - <short summary>"
git push origin vX.Y.Z
```

### 7. Watch the release workflow
Pushing the `vX.Y.Z` tag starts `.github/workflows/release.yml`: it checks the tag is on `main` and matches the project version, runs the same checks as CI, builds, smoke-tests the wheel and sdist with `scripts/smoke-dist.sh`, publishes with `uv publish --trusted-publishing always --check-url https://pypi.org/simple/`, and only then creates the GitHub Release from the CHANGELOG section for that version. Authentication is PyPI's Trusted Publisher for this repository (workflow `release.yml`, environment `pypi`), so no token is involved. The `pypi` environment may require a reviewer's approval before the publish job starts.
```bash
# A tag-triggered run has the tag as its headBranch, so select by tag rather than by
# recency: the run takes a few seconds to appear, and --limit 1 alone would return the
# PREVIOUS release's run, which is already green.
for _ in $(seq 30); do
  run="$(gh run list --repo netskopeoss/netskope-py-sdk --workflow release.yml --branch vX.Y.Z \
    --limit 1 --json databaseId -q '.[0].databaseId')"
  [ -n "$run" ] && break
  sleep 5
done
[ -n "$run" ] || { echo "no release.yml run for tag vX.Y.Z" >&2; exit 1; }
gh run watch --repo netskopeoss/netskope-py-sdk --exit-status "$run"
```
- Wait for the run to succeed. If the publish step fails, fix the cause and `gh run rerun` it; `--check-url` makes a retry skip the files PyPI already accepted instead of failing on the first duplicate.
- Fallback only, when Actions cannot run (outage, publisher not registered yet): publish locally with a token from the macOS keychain.
```bash
rm -rf dist   # uv publish uploads everything in dist/, so the previous release's files must go first
uv build
./scripts/smoke-dist.sh   # the check CI would have run on the artifacts
token="$(security find-generic-password -s pypi-netskope-py-sdk -w)" || { echo "keychain item pypi-netskope-py-sdk not found" >&2; exit 1; }
[ -n "$token" ] || { echo "empty PyPI token" >&2; exit 1; }
UV_PUBLISH_TOKEN="$token" uv publish --check-url https://pypi.org/simple/
```
- The keychain item is set up once by the user, never by AI; never echo the token. A missing or empty token must stop here: uv would otherwise upload with blank credentials and PyPI's 403 would arrive after the tag is already public.
- After a fallback publish the GitHub Release is not created either, so create it by hand with the same notes the workflow would have used:
```bash
notes="$(mktemp)"
# sed, not awk: this file is a slash command, and the argument substitution rewrites
# `$0` inside it, so an awk program that reads the current line cannot survive here.
sed -n '/^## \[X\.Y\.Z\]/,/^## \[/p' CHANGELOG.md | sed '1d;$d' >| "$notes"
[ -s "$notes" ] || { echo "no CHANGELOG section for X.Y.Z" >&2; exit 1; }
gh release create vX.Y.Z --repo netskopeoss/netskope-py-sdk --title "vX.Y.Z" --notes-file "$notes"
```

### 8. Verify
- Confirm the new version is live on PyPI. Note: `https://pypi.org/pypi/netskope-py-sdk/json` (unversioned) is CDN-cached and may show the old version for a few minutes — use the versioned endpoint `https://pypi.org/pypi/netskope-py-sdk/X.Y.Z/json` (should list 2 files) or `https://pypi.org/simple/netskope-py-sdk/` instead.
- Confirm the tag and GitHub Release exist: `gh release view vX.Y.Z --repo netskopeoss/netskope-py-sdk`
- Install the published wheel into a throwaway environment and import it, so the release is checked the way a user meets it:
  `uv run --isolated --no-project --with "netskope-py-sdk==X.Y.Z" python -c "import netskope; print(netskope.__version__)"`
- If the CLI repository pins this SDK, update its `netskope-py-sdk==` pin to the released version and re-run `uv lock` there.
- Print a summary of what was done

## Important
- Never hardcode or echo API tokens, PyPI tokens, or secrets
- If any step fails, stop and report the error — do not continue blindly
- Always run ruff check, ruff format, ty, and the test suite before committing
- `uv.lock` is committed. A dependency bump edits the constraint in `pyproject.toml` and then runs `uv lock`; commit both files together
