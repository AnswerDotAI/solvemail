from fastcore.utils import *
from pathlib import Path
import os,sys,webbrowser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

__all__ = ['df_scopes','oauth_creds','svc_acct_creds','gmail_service','browser_available']

df_scopes = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.labels',
]

def browser_available():
    "Check if a browser can be opened in current environment"
    if os.environ.get('NO_BROWSER'): return False
    if os.environ.get('SSH_CONNECTION') and not os.environ.get('DISPLAY'): return False
    if os.path.exists('/.dockerenv'): return False
    if os.environ.get('container'): return False
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'): return False
    try: webbrowser.get(); return True
    except webbrowser.Error: return False

def oauth_creds(creds_path='credentials.json',token_path='token.json',scopes=None,interactive=True,port=0,host='localhost',flow='auto'):
    "OAuth creds from `creds_path`/`token_path` for `scopes`. `flow` can be 'auto', 'browser', or 'console'"
    scopes = ifnone(scopes,df_scopes)
    creds_path,token_path = Path(creds_path),Path(token_path)
    creds = Credentials.from_authorized_user_file(str(token_path),scopes) if token_path.exists() else None
    if creds and creds.valid: return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds
    if not interactive: raise ValueError('Missing or invalid token, and `interactive=False`')
    auth_flow = InstalledAppFlow.from_client_secrets_file(str(creds_path),scopes=scopes)
    use_browser = flow=='browser' or (flow=='auto' and browser_available())
    if use_browser: creds = auth_flow.run_local_server(port=port,host=host)
    else: creds = auth_flow.run_console()
    token_path.write_text(creds.to_json())
    return creds

def svc_acct_creds(sa_path,scopes=None,subject=None):
    "Service account creds from `sa_path`, optionally delegated to `subject`"
    scopes = ifnone(scopes,df_scopes)
    creds = service_account.Credentials.from_service_account_file(str(sa_path),scopes=scopes)
    return creds.with_subject(subject) if subject else creds

def gmail_service(creds,cache_discovery=False):
    "Build a Gmail API service from `creds`"
    return build('gmail','v1',credentials=creds,cache_discovery=cache_discovery)
