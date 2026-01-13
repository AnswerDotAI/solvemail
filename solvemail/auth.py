from fastcore.utils import *
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

__all__ = ['df_scopes','oauth_creds','svc_acct_creds','gmail_service']

df_scopes = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.labels',
]

def oauth_creds(creds_path='credentials.json',token_path='token.json',scopes=None,interactive=True,port=0,host='localhost'):
    "OAuth creds from `creds_path`/`token_path` for `scopes`"
    scopes = ifnone(scopes,df_scopes)
    creds_path,token_path = Path(creds_path),Path(token_path)
    creds = Credentials.from_authorized_user_file(str(token_path),scopes) if token_path.exists() else None
    if creds and creds.valid: return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds
    if not interactive: raise ValueError('Missing or invalid token, and `interactive=False`')
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path),scopes=scopes)
    creds = flow.run_local_server(port=port,host=host)
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
