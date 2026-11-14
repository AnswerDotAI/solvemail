import subprocess,sys
from solvemail.email import b64e,b64d,mk_email,raw_email,parse_raw

def test_mime_roundtrip():
    data = b'abc123\x00\xff'
    assert b64d(b64e(data)) == data
    m = mk_email(to='a@example.com',subj='s',body='hi',html='<b>hi</b>',att=[('x.bin',data,'application/octet-stream')])
    restored = parse_raw(raw_email(m))
    assert restored['To'] == 'a@example.com'
    assert restored['Subject'] == 's'
    assert restored.get_body(preferencelist=('plain',)).get_content().strip() == 'hi'
    assert restored.get_body(preferencelist=('html',)).get_content().strip() == '<b>hi</b>'
    [attachment] = restored.iter_attachments()
    assert attachment.get_content() == data

def test_send_audit():
    subprocess.run([sys.executable,'-c',r'''
import sys,pytest
from google.auth.credentials import AnonymousCredentials
from solvemail import Gmail,Draft,Email

class NetworkBlocked(RuntimeError): pass

events = []
def audit(event,args):
    if event in ('solvemail.send','solvemail.senddraft'):
        events.append((event,args))
        raise PermissionError
    if event in ('socket.connect','socket.getaddrinfo'): raise NetworkBlocked

sys.addaudithook(audit)
g = Gmail(AnonymousCredentials())
with pytest.raises(PermissionError): g.send(to='a@example.com',body='hi')
with pytest.raises(PermissionError): Draft(g,id='d1').send()
assert events == [('solvemail.send',('a@example.com','hi')),('solvemail.senddraft',('d1',))]
e = Email(g,d={'payload': {'headers': [{'name': 'List-Unsubscribe', 'value': '<mailto:self@example.com?subject=bye>'}]}})
with pytest.raises(NetworkBlocked): e.unsubscribe()
assert len(events) == 2
'''],check=True)


def test_init_solveit_broker(monkeypatch, tmp_path):
    import json, threading
    from datetime import datetime, timedelta, timezone
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from google.auth.credentials import AnonymousCredentials
    import solvemail

    class Broker(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/gmail_token' or self.headers.get('Authorization') != 'test-owner':
                return self.send_error(401)
            expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            data = dict(access_token='at-1', expiry=expiry.isoformat(), email='test@example.com', scopes=solvemail.df_scopes)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(solvemail, '_g', None)
    monkeypatch.setenv('AAI_USER_KEY', 'test-owner')
    with HTTPServer(('127.0.0.1', 0), Broker) as server:
        monkeypatch.setenv('SOLVELP_URL', f'http://127.0.0.1:{server.server_port}')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            solvemail.init()
            creds = solvemail.g().creds
            assert creds.valid and creds.token == 'at-1' and creds.email == 'test@example.com'
        finally:
            server.shutdown()
            thread.join()

    local = AnonymousCredentials()
    monkeypatch.setattr(solvemail, 'oauth_creds', lambda **kw: local)
    solvemail.init(creds=local)
    assert solvemail.g().creds is local
    solvemail.init(token_path='another-account.json')
    assert solvemail.g().creds is local
    (tmp_path/'token.json').touch()
    solvemail.init()
    assert solvemail.g().creds is local
