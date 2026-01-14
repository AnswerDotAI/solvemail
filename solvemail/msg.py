from fastcore.utils import *
import base64,re,mimetypes
from pathlib import Path
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
from email.utils import formatdate,make_msgid

__all__ = ['b64e','b64d','mk_email','raw_msg','parse_raw','hdrs_dict','walk_parts','txt_part','html_part','att_parts']

def b64e(b):
    "Base64url encode `b` (bytes or str) without padding"
    if isinstance(b,str): b = b.encode()
    return base64.urlsafe_b64encode(b).decode().rstrip('=')

def b64d(s):
    "Base64url decode `s`"
    if isinstance(s,str): s = s.encode()
    s += b'='*((4-len(s)%4)%4)
    return base64.urlsafe_b64decode(s)

def _as_addr(x): return ', '.join(map(str,L(x))) if is_listy(x) else x

def mk_email(
    to:str=None,       # Recipient email address(es), comma-separated
    subj:str=None,     # Subject line
    body:str=None,     # Plain text body
    html:str=None,     # HTML body
    cc:str=None,       # CC recipient(s), comma-separated
    bcc:str=None,      # BCC recipient(s), comma-separated
    frm:str=None,      # From address
    reply_to:str=None, # Reply-To address
    headers:dict=None, # Additional headers dict
    msgid:str=None,    # Message-ID header
    date:bool=True,    # Include Date header?
    att:list[str]=None      # Attachments
) -> EmailMessage:     # Constructed email message
    "Create an `EmailMessage` from `to`,`subj`,`body`,`html`"
    m = EmailMessage()
    if frm:      m['From'] = frm
    if to:       m['To'] = _as_addr(to)
    if cc:       m['Cc'] = _as_addr(cc)
    if bcc:      m['Bcc'] = _as_addr(bcc)
    if reply_to: m['Reply-To'] = reply_to
    if subj:     m['Subject'] = subj
    if date:     m['Date'] = formatdate(localtime=True)
    m['Message-ID'] = msgid or make_msgid()
    for k,v in (headers or {}).items(): m[k] = v
    body = ifnone(body,'')
    m.set_content(body)
    if html: m.add_alternative(html,subtype='html')
    for a in L(att): _add_att(m,a)
    return m

def _add_att(m,a):
    if a is None: return
    if isinstance(a,(str,Path)): a = Path(a)
    if isinstance(a,Path):
        mt,_ = mimetypes.guess_type(a.name)
        maintype,subtype = (mt or 'application/octet-stream').split('/',1)
        m.add_attachment(a.read_bytes(),maintype=maintype,subtype=subtype,filename=a.name)
        return
    if len(a)==2:
        fn,data = a
        mt = None
    else: fn,data,mt = a
    mt = mt or mimetypes.guess_type(fn)[0] or 'application/octet-stream'
    maintype,subtype = mt.split('/',1)
    m.add_attachment(data,maintype=maintype,subtype=subtype,filename=fn)

def raw_msg(m): return b64e(m.as_bytes())
def parse_raw(raw): return BytesParser(policy=policy.default).parsebytes(b64d(raw))
def hdrs_dict(hdrs): return {h['name'].lower():h['value'] for h in (hdrs or [])}

def walk_parts(p):
    "Yield all MIME parts in a Gmail `payload`"
    if not p: return
    yield p
    for c in p.get('parts',[]) or []: yield from walk_parts(c)

def txt_part(p):
    "Return first text/plain part from `payload`"
    for o in walk_parts(p):
        if o.get('mimeType')=='text/plain' and 'data' in o.get('body',{}):
            return b64d(o['body']['data']).decode(errors='replace')
    return None

def html_part(p):
    "Return first text/html part from `payload`"
    for o in walk_parts(p):
        if o.get('mimeType')=='text/html' and 'data' in o.get('body',{}):
            return b64d(o['body']['data']).decode(errors='replace')
    return None

def att_parts(p):
    "Return attachment parts from `payload`"
    return L(walk_parts(p)).filter(lambda o: o.get('filename') and o.get('body',{}).get('attachmentId'))

