from fastcore.utils import *
from . import auth,core
from .auth import *
from .core import *

__all__ = ['init','g'] + auth.__all__ + core.__all__

_g = None

def init(creds=None,creds_path='credentials.json',token_path='token.json',scopes=None,user_id='me',interactive=True,**kwargs):
    "Create a global `Gmail` client using `creds_path`/`token_path` and `scopes`"
    global _g
    _g = Gmail(creds=creds,creds_path=creds_path,token_path=token_path,scopes=scopes,user_id=user_id,interactive=interactive,**kwargs)
    return _g

def g():
    "Return the global `Gmail` client"
    if _g is None: raise AttributeError('Call solvemail.init(...) first')
    return _g

def __getattr__(k):
    if _g is None: raise AttributeError('Call solvemail.init(...) first')
    return getattr(_g,k)
