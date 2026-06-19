"""Load this skill when an agent needs to read, search, and organize Gmail using solvemail. It covers connecting to Gmail, searching messages and threads, reading bodies and attachments, and managing labels. Sending, replying, forwarding, and trashing are documented for reference but are not enabled by default.

Connections use the `Gmail` client: `gmail = Gmail(scopes='readonly')`. Scopes control what the underlying OAuth token may do — `'readonly'` for reading and searching, `'modify'` to also add and remove labels, or `'full'` for everything including permanent deletion. The first connection opens a browser to authorize, then caches the token so later runs don't re-prompt. `gmail.profile()` returns the account profile, with the address on its `email` attribute.

solvemail is organized around four resource types:

- **Email** — a single message, with headers (from, to, subject, date), a body, labels, and optional attachments.
- **Thread** — a conversation: an email and its replies grouped under one id, holding its messages as a list of `Email` objects.
- **Draft** — an unsent message. `Draft` subclasses `Email`, so everything that works on an email works on a draft too.
- **Label** — Gmail's version of folders/tags, both system labels (`INBOX`, `UNREAD`, `STARRED`) and your own custom ones.

Fetching is lazy. An `Email` or `Thread` starts as just an id and fills in only as needed. How much comes back depends on the `fmt` you ask for: `metadata` brings headers and a snippet (enough for a listing), `full` brings the whole payload including the body and attachments, `minimal` gives just ids and labels, and `raw` gives the original RFC 2822 bytes. Reading a header lazily fetches at `metadata`; reading a body upgrades to `full`.

All solvemail methods are async, so `await` them.

# Searching

Search uses Gmail's own query syntax — the same as the Gmail search box. Common operators: `from:foo@bar.com`, `to:me`, `subject:invoice`, `has:attachment`, `is:unread`, `is:starred`, `label:Receipts`, `in:inbox`, and date filters like `after:2026/01/01` or `newer_than:7d`. Combine them freely, e.g. `from:stripe has:attachment newer_than:30d`.

`gmail.search(q, max_results=20)` returns a list of `Email` objects, each refreshed to `metadata` so you get senders, subjects, dates, and snippets without a second fetch:

    ems = await gmail.search('from:stripe has:attachment', max_results=10)

`gmail.search_threads(q, max_results=10)` works the same way but returns whole conversations as `Thread` objects, which is usually what you want when replies matter:

    ths = await gmail.search_threads('subject:invoice newer_than:30d')

`gmail.search_drafts(q, max_results=10)` lists drafts as `Draft` objects.

Search is keyword-driven and is not proof of absence. If a search comes back empty, try alternate terms — sender domains, usernames, filenames, error strings — before concluding something isn't there.

# Reading emails and threads

Once you have an `Email`, three helpers get you the body at different levels of cleanup:

- **`await e.text`** — the raw `text/plain` body, as the sender wrote it (a property, no parens).
- **`await e.html(clean=True)`** — the `text/html` body. With `clean=True` it strips Gmail signature blocks and quoted reply chains, leaving just the new content. Falls back to the text part wrapped in `<pre>` if there's no HTML.
- **`await e.body(clean=True)`** — the cleaned HTML flattened back to readable plain text. This is usually what you want for reading or feeding to an LLM.

A `Thread` holds its messages as `Email` objects on `.emails`, and `t.last` is the most recent. Index into it directly (`t.emails[0]`) and use everything above on each message:

    th = await gmail.search_threads('subject:invoice')
    last = th[0].last
    print(await last.body())

Headers are available as attributes once fetched: `e.frm`, `e.to`, `e.subj`, `e.date`, plus `e.labelIds` for the labels on the message.

# Attachments

Attachments show up as extra parts in an email's payload. `await e.attachments` pulls them out as `EmailAttachment` objects, giving you attribute access to `filename`, `mimeType`, and `body.size`. A thread's `await t.attachments` gathers them across every message in the conversation.

Each attachment is lazy — the bytes aren't downloaded until you call `await att.fetch()`. Pass `save=` a directory or filename to write it straight to disk instead of holding the bytes in memory:

    atts = await em.attachments
    data = await atts[0].fetch()              # bytes in memory
    await atts[0].fetch(save='~/Downloads')   # write to a folder

To find emails that carry files in the first place, search with `has:attachment` (or `has:drive`, `has:document`, etc). Inspect `filename`, `mimeType`, and `body.size` before fetching, and only pull the bytes when the task actually needs them.

# Sending, replying, forwarding (not enabled by default)

These are write operations. They're documented here so you understand the API, but they're not in this skill's allowed set — ask the user to enable them deliberately if the task requires it.

**Send** a new message. Body is markdown (auto-converted to HTML); pass `att=` a list of file paths to attach:

    await gmail.send(to='a@b.com', subj='Hi', body='Hello from **solvemail**!', att=['report.pdf'])

**Reply** keeps the conversation threaded — it sets the right `In-Reply-To`/`References` headers and `Re:` subject for you. Use `reply` on an `Email` or `Thread` to send straight away, or `reply_draft` to create a draft you can review first. Pass `reply_all=True` to cc the other recipients:

    await em.reply(body='Thanks, got it!')
    dr = await th.reply_draft(body='Looking into this.', reply_all=True)

**Forward** pastes the original content into a new message with a `Fwd:` subject, re-attaching the original files. Forwarding from an `Email` includes every message in the thread up to and including itself; from a `Thread` it forwards from the last message:

    await em.forward(to='c@d.com', body='FYI, see below')

A **draft** can be updated with `await dr.update_draft(body='new text')` and sent with `await dr.send()`.

# Labels and organizing

Labels are Gmail's tags. System labels (`INBOX`, `STARRED`, `UNREAD`) use their name as their id; custom labels have an id like `Label_42` that differs from their name. You can pass either a name or an id anywhere a label is expected — solvemail resolves names to ids for you.

List and look up labels:

    lbls = await gmail.labels()
    lbl  = await gmail.label('Receipts')        # by name or id
    hits = await gmail.find_labels('rec')       # substring match

Add or remove labels on an `Email` or `Thread` with `modify`, and there are shortcuts for the common ones:

    await em.modify(add='Receipts', rm='INBOX')
    await em.mark_read()       # rm UNREAD
    await em.star()            # add STARRED
    await em.archive()         # rm INBOX

Create and rename custom labels with `await gmail.create_label('Receipts')` and `await lbl.rename('Invoices')`.

Gmail treats trashing and deleting differently. Trashing moves a message or thread to the `TRASH` label, where Gmail keeps it for 30 days before purging it; `untrash` reverses that, so it's recoverable. Deleting is permanent and needs the `'full'` scope.

These are write operations and are **not enabled by default**:

    await em.trash()       # recoverable
    await em.untrash()
    await em.delete()      # permanent, requires 'full' scope

# Unsubscribe

Well-behaved senders include a `List-Unsubscribe` header describing how to opt out — either a `mailto:` address to email or a URL to POST to (flagged one-click by `List-Unsubscribe-Post`). `await em.unsubscribe()` reads that header and does whichever the sender offered, so you don't have to hunt for the link buried in the message. On a `Thread`, it unsubscribes using the last message.

Note that the `mailto:` path sends an email, so this is a write operation and is not enabled by default.

# Gotchas

All solvemail methods are async — `await` them, including the `text` property (`await e.text`).

`text` is a property (no parens), but `html()` and `body()` are methods that take a `clean` argument.

Fetching is lazy and `fmt`-dependent. Search returns emails at `metadata` (headers + snippet); reading a body upgrades that message to `full`. If a body looks empty, the message may only be at `metadata` — reading `body()`/`html()`/`text` will fetch the full payload for you.

Scopes gate what you can do: `'readonly'` can't change labels, and permanent `delete` needs `'full'`. A permission error usually means the client was created with too narrow a scope.

Search is keyword-driven and can miss messages or return thin snippets — treat it as a way to gather candidates, not proof that something does or doesn't exist.

Dates are strings, not datetime objects."""
from pyskills.core import allow
from solvemail.core import (Gmail, Email, Emails, Thread, Threads,
                            Draft, Drafts, Label, EmailAttachment)

__all__ = ['Gmail', 'Email', 'Emails', 'Thread', 'Threads',
           'Draft', 'Drafts', 'Label', 'EmailAttachment']

allow({Gmail: ['profile', 'search', 'search_threads', 'search_drafts', 'create_draft',
               'labels', 'label', 'find_labels', 'create_label', 'lbl_ids'],
       Email: ['refresh', 'html', 'body', 'modify',
               'mark_read', 'mark_unread', 'star', 'unstar', 'archive', 'inbox'],
       Thread: ['refresh', 'modify',
                'mark_read', 'mark_unread', 'star', 'unstar', 'archive', 'inbox'],
       Label: ['refresh', 'rename'],
       EmailAttachment: ['fetch']})