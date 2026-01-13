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
for m in t.msgs():
    print(m.frm, '|', m.subj)

# Read a message
m = t.msgs()[0]
m.subj, m.frm, m.snip, m.text()

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

# Search individual messages
search_msgs('has:attachment filename:pdf', max_results=100)
```

### Messages

```python
m = msg(id)           # Fetch by id
m.subj, m.frm, m.to             # Headers
m.text(), m.html()              # Body content
m.mark_read(), m.mark_unread()  # Read status
m.star(), m.unstar()            # Starred
m.archive()                     # Remove from inbox
m.trash(), m.untrash()          # Trash
m.add_labels('MyLabel')         # Add labels
m.rm_labels('INBOX')            # Remove labels
```

### Threads

```python
t = thread(id)        # Fetch by id
t.msgs()                        # List messages
t.reply_draft(body='...')       # Create reply draft
t.reply(body='...')             # Send reply directly
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
# Batch modify labels (auto-chunks, no 1000 message limit)
ids = [m.id for m in search_msgs('in:inbox')]
batch_label(ids, add=['SPAM'], rm=['INBOX'])

# Trash multiple messages
trash_msgs(ids)
```

## Using the Gmail class directly

```python
from solvemail import Gmail

g = Gmail(creds_path='credentials.json', token_path='token.json')
lbl = g.create_label('test-label')

m = g.send(to=g.profile().email, subj='hello', body='hi there')
m.add_labels(lbl)

lbl.delete()
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

