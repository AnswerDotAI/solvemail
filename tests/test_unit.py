import sys
from fastcore.test import test_eq as eq
from solvemail.email import b64e,b64d,mk_email,raw_email,parse_raw
from solvemail.core import Gmail,Email,Draft

def test_b64_roundtrip():
    b = b'abc123\x00\xff'
    eq(b64d(b64e(b)),b)

def test_email_roundtrip():
    m = mk_email(to='a@example.com',subj='s',body='hi',html='<b>hi</b>')
    m2 = parse_raw(raw_email(m))
    eq(m2['To'],'a@example.com')
    eq(m2['Subject'],'s')

def test_send_audits(monkeypatch):
    events,sent = [],[]
    monkeypatch.setattr(sys,'audit',lambda *o: events.append(o))
    g = object.__new__(Gmail)
    g._send = lambda email,thread_id=None: sent.append((email,thread_id)) or 'sent'
    eq(Gmail.send(g,to='a@example.com',subj='s',body='hi',thread_id='t'),'sent')
    eq(events,[('solvemail.send','a@example.com','hi')])
    eq(sent[0][0]['To'],'a@example.com')
    eq(sent[0][1],'t')

def test_draft_send_audits(monkeypatch):
    events = []
    monkeypatch.setattr(sys,'audit',lambda *o: events.append(o))
    class _Drafts:
        def send(self,userId,body):
            self.body = body
            return body
    class _Users:
        def __init__(self): self.ds = _Drafts()
        def drafts(self): return self.ds
    class _Gmail:
        user_id = 'me'
        def __init__(self): self._u = _Users()
        def _exec(self,req): return {'id':'m1'}
    g = _Gmail()
    eq(Draft(g,id='d1').send().id,'m1')
    eq(events,[('solvemail.senddraft','d1')])
    eq(g._u.ds.body,{'id':'d1'})

def test_unsubscribe_mailto_does_not_audit(monkeypatch):
    events,sent = [],[]
    monkeypatch.setattr(sys,'audit',lambda *o: events.append(o))
    class _Gmail:
        def _send(self,email,thread_id=None):
            sent.append((email,thread_id))
            return 'sent'
    d = {'payload': {'headers': [{'name':'List-Unsubscribe','value':'<mailto:unsub@example.com?subject=bye>'}]}}
    eq(Email(_Gmail(),d=d).unsubscribe(),'sent')
    eq(events,[])
    eq(sent[0][0]['To'],'unsub@example.com')
    eq(sent[0][0]['Subject'],'bye')
    eq(sent[0][0].get_content().strip(),'unsubscribe')
