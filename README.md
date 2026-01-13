# solvemail

`solvemail` is a small Gmail / Google Workspace email client built on the official Gmail API Python client, with a convenience layer inspired by `ezgmail`, using the fastai/fastcore coding style.

## Install

```bash
pip install -e ".[dev]"
```

(or `pip install solvemail` once you publish it)

## OAuth setup

1. Create an OAuth Client ID (Desktop app) in Google Cloud Console and enable the Gmail API.
2. Download the client secrets JSON as `credentials.json`.
3. Put `credentials.json` next to your script (or pass its path).

On first run, `solvemail` will open a browser to authorize and will write `token.json`.

## Quick start

```python
import solvemail

solvemail.init()  # reads credentials.json + token.json in cwd by default

threads = solvemail.search('is:unread newer_than:7d', max_results=10)
t = threads[0].get()
m = t.msgs()[-1].get(fmt='metadata')

m.subj, m.frm, m.snip

m.mark_read()
m.archive()

r = t.reply_draft(body='Thanks!\n\n- me')
r.send()
```

## Using the class directly

```python
from solvemail import Gmail

g = Gmail(creds_path='credentials.json', token_path='token.json')
lbl = g.create_label('solvemail-test')

m = g.send(to=g.profile().email, subj='hello', body='hi there')
m.add_labels(lbl)

lbl.delete()
```

## End-to-end tests

Set these env vars to run e2e tests against a throwaway Gmail/Workspace account:

- `GMAILX_CREDS` path to `credentials.json`
- `GMAILX_TOKEN` path to `token.json` (will be created if missing and tests run interactively)
- `GMAILX_E2E` set to `1` to enable e2e tests

Then:

```bash
pytest -q
```

The tests create a temporary label, send mail to the authenticated account, create a reply draft in the same thread, send it, and clean up.

