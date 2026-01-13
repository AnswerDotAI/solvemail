from fastcore.test import test_eq
from solvemail.msg import b64e,b64d,mk_email,raw_msg,parse_raw

def test_b64_roundtrip():
    b = b'abc123\x00\xff'
    test_eq(b64d(b64e(b)),b)

def test_email_roundtrip():
    m = mk_email(to='a@example.com',subj='s',body='hi',html='<b>hi</b>')
    m2 = parse_raw(raw_msg(m))
    test_eq(m2['To'],'a@example.com')
    test_eq(m2['Subject'],'s')
