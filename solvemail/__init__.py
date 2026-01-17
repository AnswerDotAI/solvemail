__version__ = "0.1.5"

from fastcore.utils import *
from functools import wraps
from inspect import signature
from . import auth,core
from .auth import *
from .core import *
import time

__all__ = [
    'init','g','solvemail_tools','refresh_solvemail','wait_secs'
    ] + auth.__all__ + core.__all__ + [
    k for k in dir(Gmail) if not k.startswith('_')]

def __dir__(): return __all__

_g = None

def _proxy(name):
    method = getattr(Gmail, name)
    @wraps(method)
    def fn(*a, **kw): return getattr(g(), name)(*a, **kw)
    return fn

def refresh_solvemail():
    "Reload Gmail methods"
    for _k in dir(Gmail):
        if callable(getattr(Gmail, _k)) and not _k.startswith('_'): globals()[_k] = _proxy(_k)

refresh_solvemail()

def init(creds=None, creds_path='credentials.json', token_path='token.json', scopes=None, user_id='me',
         interactive=True, redirect_uri=None, retries=3):
    "Create a global `Gmail` client using `creds_path`/`token_path` and `scopes`"
    global _g
    if creds is None: creds = oauth_creds(creds_path=creds_path, token_path=token_path, scopes=scopes, interactive=interactive, redirect_uri=redirect_uri)
    _g = Gmail(creds=creds, user_id=user_id, retries=retries)

def g():
    "Return the global `Gmail` client"
    if _g is None: raise AttributeError('Call solvemail.init(...) first')
    return _g

def solvemail_tools(): return '&`[search_threads, search_msgs, thread, draft, drafts, labels, label, find_labels, profile, send, reply_draft, reply_to_thread, create_label, trash_msgs, view_inbox, view_inbox_threads, view_msg, view_thread, batch_delete, batch_label, message, send_drafts, report_spam]`'

def wait_secs(secs: float = 1.0):
    "Pause for `secs` seconds; use if rate limited"
    time.sleep(secs)
    return f"Waited {secs}s"

