# Development

## Quick PRs

Use `qpr` to create, merge, and cleanup a PR in one command:

```bash
./qpr "commit message" [label]
```

Labels: `enhancement` (default), `bug`, `breaking`

## Testing

Set env vars and run pytest:

```bash
export GMAILX_CREDS=path/to/credentials.json
export GMAILX_TOKEN=path/to/token.json
export GMAILX_E2E=1
pytest -q
```

## Releasing

Creates a GitHub release and publishes to PyPI:

```bash
./release patch  # or minor, major
```
