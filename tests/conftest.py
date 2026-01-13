import os,pytest
from solvemail import Gmail

def _env(k,df=None):
    v = os.environ.get(k,df)
    return v if v not in ('',None) else None

@pytest.fixture(scope='session')
def g():
    if _env('GMAILX_E2E')!='1': pytest.skip('Set GMAILX_E2E=1 to run e2e tests')
    creds = _env('GMAILX_CREDS','credentials.json')
    token = _env('GMAILX_TOKEN','token.json')
    interactive = _env('GMAILX_INTERACTIVE','1')=='1'
    return Gmail(creds_path=creds,token_path=token,interactive=interactive)
