# solvemail

A simple Gmail / Google Workspace email client built on the official Gmail API, using the fastai/fastcore coding style.

## Install

```bash
pip install solvemail
```

Or for development:

```bash
pip install -e .
```

## OAuth setup

For detailed instructions on setting up Google Cloud credentials, see [ezgmail's excellent documentation](https://github.com/asweigart/ezgmail#enable-the-gmail-api).

In brief:

1. Create an OAuth Client ID (Desktop app) in [Google Cloud Console](https://console.cloud.google.com) and enable the Gmail API
2. Download the client secrets JSON as `credentials.json`
3. Put `credentials.json` next to your script (or pass its path)

On first run, `solvemail` will open a browser to authorize and will save `token.json`.

## Quick start

```python
import solvemail

solvemail.init()  # reads credentials.json + token.json in cwd

# For multiple accounts, use separate token files:
# solvemail.init(token_path='work.json')    # first run opens browser to auth
# solvemail.init(token_path='personal.json') # switch account without re-auth

# Check which account you're using
solvemail.profile().email

# solvemail exports the key API functionality through wildcard import
from solvemail import *

# Search for threads
threads = search_threads('is:unread newer_than:7d', max_results=10)

# Get thread details
t = threads[0]
for e in t.emails():
    print(e.frm, '|', e.subj)

# Read an email
e = t.emails()[0]
e.subj, e.frm, e.snip, e.text()

# Send an email
send(to='someone@example.com', subj='Hello', body='Hi there!')

# Create and send a reply
draft = t.reply_draft(body='Thanks!')
draft.send()
```

## Features

### Searching

```python
# Search threads (conversations)
search_threads('from:boss@company.com', max_results=20)

# Search individual emails
search_emails('has:attachment filename:pdf', max_results=100)
```

### Emails

```python
e = email(id)         # Fetch by id
e.subj, e.frm, e.to             # Headers
e.text(), e.html()              # Body content
e.mark_read(), e.mark_unread()  # Read status
e.star(), e.unstar()            # Starred
e.archive()                     # Remove from inbox
e.trash(), e.untrash()          # Trash
e.add_labels('MyLabel')         # Add labels
e.rm_labels('INBOX')            # Remove labels
```

### Threads

```python
t = thread(id)        # Fetch by id
t.emails()                      # List emails
t[0], t[-1]                     # Index into emails
t.reply_draft(body='...')       # Create reply draft
t.reply(body='...')             # Send reply directly

# Batch fetch multiple threads efficiently (one HTTP call)
threads = search_threads('in:inbox', max_results=50)
threads = get_threads(threads)
```

### Email Display

Emails render nicely in Jupyter notebooks (quotes and signatures stripped automatically).

```python
e = t[-1]
e.body()   # Cleaned text (no quotes/signatures)
e.html()   # HTML body (falls back to text wrapped in <pre>)

# View email with headers (as dict or plain text)
view_email(e.id)                    # Returns dict with headers + body
view_email(e.id, as_json=False)     # Returns formatted text

# View full thread
view_thread(t.id)                   # Dict of email id -> email dict
view_thread(t.id, as_json=False)    # Concatenated text with separators
```

### Inbox helpers

```python
view_inbox(max_emails=20)           # Batch fetch inbox emails
view_inbox_threads(max_threads=20)  # Batch fetch inbox threads
view_inbox(unread=True)             # Only unread
```

### Labels

```python
labels()                        # List all labels
label('INBOX')                  # Get by name or id
find_labels('project')          # Search labels
create_label('My Label')        # Create new label
```

### Drafts

```python
drafts()                        # List drafts
create_draft(to='...', subj='...', body='...')
reply_to_thread(thread_id, body='...')
```

### Bulk operations

```python
# Batch modify labels (auto-chunks, no 1000 email limit)
ids = [e.id for e in search_emails('in:inbox')]
batch_label(ids, add=['SPAM'], rm=['INBOX'])

# Trash multiple emails
trash_emails(ids)

# Permanently delete (requires full mail scope)
batch_delete(ids)
```

## Testing

Set these env vars to run e2e tests against a throwaway Gmail/Workspace account:

- `GMAILX_CREDS` — path to `credentials.json`
- `GMAILX_TOKEN` — path to `token.json` (will be created if missing)
- `GMAILX_E2E` — set to `1` to enable e2e tests

```bash
pytest -q
```

## Credits

Inspired by [ezgmail](https://github.com/asweigart/ezgmail) by [Al Sweigart](https://inventwithpython.com/) — thanks Al for the great work! The ezgmail repo also has excellent documentation on setting up Gmail API credentials.
