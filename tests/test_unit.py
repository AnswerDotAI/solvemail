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
