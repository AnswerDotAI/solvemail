from fastcore.utils import *
from fastcore.meta import *
import re,time,html,httpx
from bs4 import BeautifulSoup
from googleapiclient.errors import HttpError
from .auth import gmail_service
from .msg import b64d,mk_email,raw_msg,parse_raw,hdrs_dict,att_parts,txt_part,html_part

__all__ = ['Gmail','Label','Msg','Thread','Draft']

_sys_lbls = {o for o in 'INBOX SPAM TRASH UNREAD STARRED IMPORTANT SENT DRAFT CHAT CATEGORY_FORUMS CATEGORY_UPDATES CATEGORY_PERSONAL CATEGORY_PROMOTIONS CATEGORY_SOCIAL'.split()}

def _as_id(o,attr='id'): return getattr(o,attr) if hasattr(o,attr) else o
def _norm_lbl(l): return l.upper() if isinstance(l,str) and l.upper() in _sys_lbls else l
def _uniq(xs): return L(xs).filter().unique().items
def _exp_backoff(i,base=0.25,cap=4): time.sleep(min(cap,base*(2**i)))

class Label:
    def __init__(self,gmail,d): store_attr('gmail,d')
    def __repr__(self): return f'Label({self.id}:{self.name})'
    @property
    def id(self): return self.d.get('id')
    @property
    def name(self): return self.d.get('name')
    @property
    def is_sys(self): return self.d.get('type')=='system' or self.id in _sys_lbls

    def refresh(self):
        "Reload this label"
        self.d = self.gmail._exec(self.gmail._u.labels().get(userId=self.gmail.user_id,id=self.id))
        self.gmail._lbls = None
        return self

    def delete(self):
        "Delete this label"
        res = self.gmail._exec(self.gmail._u.labels().delete(userId=self.gmail.user_id,id=self.id))
        self.gmail._lbls = None
        return res

    def patch(self,**kwargs):
        "Patch this label using `kwargs`"
        self.d = self.gmail._exec(self.gmail._u.labels().patch(userId=self.gmail.user_id,id=self.id,body=kwargs))
        self.gmail._lbls = None
        return self

    def rename(self,name):
        "Rename this label to `name`"
        return self.patch(name=name)

class Msg:
    def __init__(self,gmail,id=None,d=None):
        store_attr('gmail')
        self.d = d or {}
        self._id = ifnone(id,self.d.get('id'))
        self._cache = {}

    def __repr__(self):
        if not self.d.get('payload'): return f'Msg({self.id})'
        lbls = ','.join(self.label_ids) if self.label_ids else ''
        return f'Msg({self.id}: [{lbls}] {self.frm} | {self.subj}\n{self.snip})'

    @property
    def id(self): return self._id
    @property
    def thread_id(self): return self.d.get('threadId')
    @property
    def label_ids(self): return L(self.d.get('labelIds',[]))
    @property
    def snip(self): return html.unescape(self.d.get('snippet') or '')

    def get(self,
        fmt:str='full',           # Format: 'full', 'metadata', 'minimal', or 'raw'
        metadata_headers=None     # Headers to include in metadata format
    ):
        "Fetch message data from Gmail"
        body = dict(userId=self.gmail.user_id,id=self.id,format=fmt)
        if metadata_headers: body['metadataHeaders'] = L(metadata_headers).items
        self.d = self.gmail._exec(self.gmail._u.messages().get(**body))
        self._cache = {}
        return self

    def hdrs(self,
        refresh:bool=False  # Refresh from API?
    ):
        "Get lowercased headers dict"
        if refresh or 'hdrs' not in self._cache:
            if not self.d.get('payload'): self.get(fmt='metadata')
            self._cache['hdrs'] = hdrs_dict(self.d.get('payload',{}).get('headers',[]))
        return self._cache['hdrs']

    @property
    def subj(self): return self.hdrs().get('subject')
    @property
    def frm(self):  return self.hdrs().get('from')
    @property
    def to(self):   return self.hdrs().get('to')
    @property
    def msgid(self): return self.hdrs().get('message-id')
    @property
    def refs(self):  return self.hdrs().get('references')

    def _has_body(self):
        p = self.d.get('payload',{})
        return p.get('body') or p.get('parts')

    def text(self):
        "Get plain text body"
        if not self._has_body(): self.get(fmt='full')
        return txt_part(self.d.get('payload'))

    def html(self,
        clean:bool=True # strip reply quotations and signatures?
    ):
        "Get HTML body (optionally cleaned), falls back to text wrapped in pre"
        if not self._has_body(): self.get(fmt='full')
        h = html_part(self.d.get('payload'))
        if not h:
            t = txt_part(self.d.get('payload'))
            h = f'<pre>{t}</pre>' if t else None
        if not h or not clean: return h
        soup = BeautifulSoup(h, 'html.parser')
        for sig in soup.select('.gmail_signature, .gmail_signature_prefix'): sig.decompose()
        for q in soup.select('.gmail_quote'):
            prev = q.find_previous_sibling()
            if prev and prev.get_text(strip=True): q.decompose()
        return str(soup)

    def body(self,
        clean:bool=True # strip reply quotations and signatures?
    ):
        "Get (optionally cleaned) text body"
        soup = BeautifulSoup(self.html(clean=clean), 'html.parser')
        for br in soup.find_all('br'): br.replace_with('\n')
        for tag in soup.find_all(['p', 'div']): tag.append('\n')
        return re.sub(r'\n{3,}', '\n\n', soup.get_text().strip())

    def _repr_html_(self):
        h = self.hdrs()
        parts = [f"<b>From:</b> {h.get('from','')}", f"<b>Date:</b> {h.get('date','')}",
                 f"<b>To:</b> {h.get('to','')}"]
        if h.get('cc'): parts.append(f"<b>Cc:</b> {h.get('cc')}")
        if h.get('bcc'): parts.append(f"<b>Bcc:</b> {h.get('bcc')}")
        parts.append(f"<b>Subject:</b> {h.get('subject','')}")
        hdr = '<br>'.join(parts)
        return f"{hdr}<hr>{self.html(True)}"

    def raw(self,
        refresh:bool=False  # Refresh from API?
    ):
        "Get base64url raw RFC 2822 message"
        if refresh or 'raw' not in self._cache:
            d = self.gmail._exec(self.gmail._u.messages().get(userId=self.gmail.user_id,id=self.id,format='raw'))
            self._cache['raw'] = d.get('raw')
        return self._cache['raw']

    def email(self,
        refresh:bool=False  # Refresh from API?
    ):
        "Get parsed EmailMessage object"
        if refresh or 'email' not in self._cache: self._cache['email'] = parse_raw(self.raw(refresh=refresh))
        return self._cache['email']

    def modify(self,
        add:list=None,  # Label ids/names to add
        rm:list=None    # Label ids/names to remove
    ):
        "Modify labels on this message"
        add,rm = self.gmail.lbl_ids(add),self.gmail.lbl_ids(rm)
        body = dict(addLabelIds=add,removeLabelIds=rm)
        self.d = self.gmail._exec(self.gmail._u.messages().modify(userId=self.gmail.user_id,id=self.id,body=body))
        self._cache = {}
        return self

    def add_labels(self,*lbls): return self.modify(add=lbls)
    def rm_labels(self,*lbls):  return self.modify(rm=lbls)
    def mark_read(self):        return self.rm_labels('UNREAD')
    def mark_unread(self):      return self.add_labels('UNREAD')
    def star(self):             return self.add_labels('STARRED')
    def unstar(self):           return self.rm_labels('STARRED')
    def archive(self):          return self.rm_labels('INBOX')
    def inbox(self):            return self.add_labels('INBOX')

    def trash(self):
        "Move message to trash"
        self.d = self.gmail._exec(self.gmail._u.messages().trash(userId=self.gmail.user_id,id=self.id))
        self._cache = {}
        return self

    def untrash(self):
        "Remove message from trash"
        self.d = self.gmail._exec(self.gmail._u.messages().untrash(userId=self.gmail.user_id,id=self.id))
        self._cache = {}
        return self

    def delete(self):
        "Permanently delete message (requires full mail scope)"
        return self.gmail._exec(self.gmail._u.messages().delete(userId=self.gmail.user_id,id=self.id))

    def att_parts(self):
        "Return attachment parts for this message"
        if not self.d.get('payload'): self.get(fmt='full')
        return att_parts(self.d.get('payload'))

    def att(self, part):
        "Download attachment"
        part = part if isinstance(part,dict) else self.att_parts()[part]
        aid = part['body']['attachmentId']
        res = self.gmail._exec(self.gmail._u.messages().attachments().get(userId=self.gmail.user_id,messageId=self.id,id=aid))
        return b64d(res.get('data',''))

    def reply_draft(self,
        body:str=None,  # Plain text body
        html:str=None,  # HTML body
        **kwargs
    ):
        "Create a reply draft"
        return self.gmail.reply_draft(self,body=body,html=html,**kwargs)

    def reply(self,
        body:str=None,  # Plain text body
        html:str=None,  # HTML body
        **kwargs
    ):
        "Send a reply"
        return self.reply_draft(body=body,html=html,**kwargs).send()

    def unsubscribe(self):
        "Unsubscribe using List-Unsubscribe header (mailto or HTTP POST)"
        h = self.hdrs()
        unsub = h.get('list-unsubscribe')
        if not unsub: return None
        post_body = h.get('list-unsubscribe-post', 'List-Unsubscribe=One-Click')
        urls = re.findall(r'<([^>]+)>', unsub)
        for url in urls:
            if url.startswith('mailto:'):
                parts = url[7:].split('?', 1)
                to = parts[0]
                subj = dict(p.split('=',1) for p in parts[1].split('&')).get('subject','unsubscribe') if len(parts)>1 else 'unsubscribe'
                return self.gmail.send(to=to, subj=subj, body='unsubscribe')
            if url.startswith('http'):
                resp = httpx.post(url, content=post_body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                return resp
        return None

class Thread:
    def __init__(self,gmail,id=None,d=None):
        store_attr('gmail')
        self.d = d or {}
        self._id = ifnone(id,self.d.get('id'))
        self._cache = {}

    def __repr__(self):
        n = len(self.d.get('messages', []))
        if not n: return f'Thread({self.id})'
        m = Msg(self.gmail, d=self.d['messages'][-1])
        if not m.d.get('snippet'): m.get(fmt='metadata')
        lbls = ','.join(m.label_ids) if m.label_ids else ''
        return f'Thread({self.id}: {n} msgs, [{lbls}] {m.frm} -> {m.to} | {m.subj}\n{m.snip})'

    def __getitem__(self, i): return self.msgs()[i]

    @property
    def id(self): return self._id
    @property
    def hist_id(self): return self.d.get('historyId')

    def get(self,fmt='full',metadata_headers=None):
        "Fetch thread with `fmt`"
        body = dict(userId=self.gmail.user_id,id=self.id,format=fmt)
        if metadata_headers: body['metadataHeaders'] = L(metadata_headers).items
        self.d = self.gmail._exec(self.gmail._u.threads().get(**body))
        self._cache = {}
        return self

    def msgs(self,refresh=False,fmt='metadata'):
        "Return messages in this thread"
        if refresh or 'msgs' not in self._cache:
            if not self.d.get('messages'): self.get(fmt=fmt)
            self._cache['msgs'] = L(self.d.get('messages',[])).map(lambda o: Msg(self.gmail,d=o))
        return self._cache['msgs']

    def last(self): return self.msgs()[-1]

    def modify(self,add=None,rm=None):
        "Modify labels on this thread"
        add,rm = self.gmail.lbl_ids(add),self.gmail.lbl_ids(rm)
        body = dict(addLabelIds=add,removeLabelIds=rm)
        self.d = self.gmail._exec(self.gmail._u.threads().modify(userId=self.gmail.user_id,id=self.id,body=body))
        self._cache = {}
        return self

    def add_labels(self,*lbls): return self.modify(add=lbls)
    def rm_labels(self,*lbls):  return self.modify(rm=lbls)

    def trash(self):
        "Move thread to trash"
        self.d = self.gmail._exec(self.gmail._u.threads().trash(userId=self.gmail.user_id,id=self.id))
        self._cache = {}
        return self

    def untrash(self):
        "Remove thread from trash"
        self.d = self.gmail._exec(self.gmail._u.threads().untrash(userId=self.gmail.user_id,id=self.id))
        self._cache = {}
        return self

    def delete(self):
        "Permanently delete thread (requires full mail scope)"
        return self.gmail._exec(self.gmail._u.threads().delete(userId=self.gmail.user_id,id=self.id))

    def reply_draft(self,body=None,html=None,**kwargs):
        "Create a reply draft to the last message in this thread"
        return self.last().reply_draft(body=body,html=html,thread_id=self.id,**kwargs)

    def reply(self,body=None,html=None,**kwargs):
        "Send a reply to the last message in this thread"
        return self.reply_draft(body=body,html=html,**kwargs).send()

class Draft:
    def __init__(self,gmail,id=None,d=None):
        store_attr('gmail')
        self.d = d or {}
        self._id = ifnone(id,self.d.get('id'))

    def __repr__(self):
        if not self.d.get('message'): return f'Draft({self.id})'
        m = self.msg
        if m and not m.d.get('payload'): m.get(fmt='metadata')
        if not m: return f'Draft({self.id})'
        return f'Draft({self.id}: {m.to} | {m.subj}\n{m.snip})'
    @property
    def id(self): return self._id
    @property
    def msg(self):
        m = self.d.get('message',{})
        return Msg(self.gmail,id=m.get('id'),d=m) if m else None
    @property
    def thread_id(self): return (self.d.get('message') or {}).get('threadId')

    def get(self,fmt='full'):
        "Fetch draft, loading the underlying message with `fmt`"
        self.d = self.gmail._exec(self.gmail._u.drafts().get(userId=self.gmail.user_id,id=self.id,format=fmt))
        return self

    def delete(self):
        "Delete this draft"
        return self.gmail._exec(self.gmail._u.drafts().delete(userId=self.gmail.user_id,id=self.id))

    @delegates(mk_email)
    def update(self,msg=None,thread_id=None,**kwargs):
        "Update this draft with `msg` (EmailMessage) or build from kwargs"
        msg = ifnone(msg,mk_email(**kwargs))
        body = dict(message=dict(raw=raw_msg(msg)))
        if thread_id or self.thread_id: body['message']['threadId'] = ifnone(thread_id,self.thread_id)
        self.d = self.gmail._exec(self.gmail._u.drafts().update(userId=self.gmail.user_id,id=self.id,body=body))
        return self

    @delegates(mk_email)
    def send(self,msg=None,thread_id=None,**kwargs):
        "Send this draft (optionally updating message from `msg` or kwargs)"
        body = dict(id=self.id)
        if msg or kwargs:
            msg = ifnone(msg,mk_email(**kwargs))
            body['message'] = dict(raw=raw_msg(msg))
            if thread_id or self.thread_id: body['message']['threadId'] = ifnone(thread_id,self.thread_id)
        res = self.gmail._exec(self.gmail._u.drafts().send(userId=self.gmail.user_id,body=body))
        return Msg(self.gmail,d=res)

class Gmail:
    def __init__(self, creds, user_id='me', retries=3):
        "Gmail client using OAuth `creds`"
        store_attr()
        self.s = gmail_service(creds)
        self._u = self.s.users()
        self._lbls = None

    def _exec(self,req):
        for i in range(self.retries+1):
            try: return req.execute(num_retries=0)
            except HttpError as e:
                if e.resp.status in (429,500,503) and i<self.retries:
                    _exp_backoff(i)
                    continue
                raise

    def profile(self):  # Profile with `email` attribute
        "Return profile resource with `email` attribute"
        d = self._exec(self._u.getProfile(userId=self.user_id))
        return AttrDict(d,email=d.get('emailAddress'))

    def labels(self,
        refresh:bool=False  # Refresh cache?
    ):  # List of Label objects
        "List all labels"
        if refresh or self._lbls is None:
            d = self._exec(self._u.labels().list(userId=self.user_id))
            self._lbls = L(d.get('labels',[])).map(lambda o: Label(self,o))
        return self._lbls

    def label(self,
        lbl:str,            # Label id or name
        refresh:bool=False  # Refresh cache?
    ):  # Found label
        "Return label by id or name"
        lbl = _norm_lbl(lbl)
        if isinstance(lbl,Label): return lbl
        lbls = self.labels(refresh=refresh)
        by_id = {o.id:o for o in lbls}
        if lbl in by_id: return by_id[lbl]
        by_nm = {o.name:o for o in lbls}
        if lbl in by_nm: return by_nm[lbl]
        raise KeyError(f'Unknown label: {lbl}')

    def find_labels(self,
        term:str,           # Search term
        refresh:bool=False, # Refresh cache?
        regex:bool=False    # Use regex matching?
    ):  # Matching labels
        "Find labels matching `term`"
        lbls = self.labels(refresh=refresh)
        if regex:
            r = re.compile(term)
            return lbls.filter(lambda o: r.search(o.name))
        term = term.lower()
        return lbls.filter(lambda o: term in o.name.lower())

    def create_label(self,
        name:str,                              # Label name
        messageListVisibility:str='show',      # 'show' or 'hide' in message list
        labelListVisibility:str='labelShow'    # 'labelShow', 'labelShowIfUnread', or 'labelHide'
    ):  # Created label
        "Create a new label"
        d = dict(name=name,messageListVisibility=messageListVisibility,labelListVisibility=labelListVisibility)
        res = self._exec(self._u.labels().create(userId=self.user_id,body=d))
        self._lbls = None
        return Label(self,res)

    def lbl_ids(self,lbls):
        "Normalize labels (names/ids/Label) to label ids"
        if lbls is None: return []
        def _one(l):
            l = _norm_lbl(l)
            if l is None: return None
            if isinstance(l,Label): return l.id
            if isinstance(l,str) and l.upper() in _sys_lbls: return l.upper()
            try: return self.label(l).id
            except KeyError: return l
        return _uniq(L(lbls).map(_one) if is_listy(lbls) else L([lbls]).map(_one))

    def message(self,
        id:str,           # Message id
        fmt:str='full'    # Format: 'full', 'metadata', 'minimal', or 'raw'
    ):  # Fetched message
        "Fetch message by id"
        return Msg(self,id=id).get(fmt=fmt)

    def thread(self,
        id:str,           # Thread id
        fmt:str='full'    # Format: 'full', 'metadata', or 'minimal'
    ):  # Fetched thread
        "Fetch thread by id"
        return Thread(self,id=id).get(fmt=fmt)

    def draft(self,
        id:str,           # Draft id
        fmt:str='full'    # Format: 'full', 'metadata', or 'minimal'
    ):  # Fetched draft
        "Fetch draft by id"
        return Draft(self,id=id).get(fmt=fmt)

    def _list(self,fn,key,limit=None,**kwargs):
        tok,n = None,0
        while True:
            if tok: kwargs['pageToken'] = tok
            d = self._exec(fn(**kwargs))
            for o in d.get(key,[]) or []:
                yield o
                n += 1
                if limit and n>=limit: return
            tok = d.get('nextPageToken')
            if not tok: break

    def search_msgs(self,
        q:str=None,                     # Gmail search query (e.g. 'is:unread from:foo')
        label_ids:list=None,            # Filter by label ids/names
        max_results:int=50,             # Max messages to return (None for all)
        include_spam_trash:bool=False   # Include spam/trash?
    ):  # List of Msg objects
        "Search messages using Gmail query"
        page_sz = min(max_results,500) if max_results else 500
        kwargs = dict(userId=self.user_id,maxResults=page_sz,includeSpamTrash=include_spam_trash)
        if q: kwargs['q'] = q
        if label_ids: kwargs['labelIds'] = self.lbl_ids(label_ids)
        it = self._list(self._u.messages().list,'messages',limit=max_results,**kwargs)
        return L(it).map(lambda o: Msg(self,d=o))

    def search_threads(self,
        q:str=None,                     # Gmail search query (e.g. 'is:unread from:foo')
        label_ids:list=None,            # Filter by label ids/names
        max_results:int=50,             # Max threads to return (None for all)
        include_spam_trash:bool=False   # Include spam/trash?
    ):  # List of Thread objects
        "Search threads using Gmail query"
        page_sz = min(max_results,500) if max_results else 500
        kwargs = dict(userId=self.user_id,maxResults=page_sz,includeSpamTrash=include_spam_trash)
        if q: kwargs['q'] = q
        if label_ids: kwargs['labelIds'] = self.lbl_ids(label_ids)
        it = self._list(self._u.threads().list,'threads',limit=max_results,**kwargs)
        return L(it).map(lambda o: Thread(self,d=o))

    def drafts(self,
        q:str=None,          # Gmail search query
        max_results:int=50   # Max drafts to return (None for all)
    ):  # List of Draft objects
        "List drafts"
        page_sz = min(max_results,500) if max_results else 500
        kwargs = dict(userId=self.user_id,maxResults=page_sz)
        if q: kwargs['q'] = q
        it = self._list(self._u.drafts().list,'drafts',limit=max_results,**kwargs)
        return L(it).map(lambda o: Draft(self,d=o))

    @delegates(mk_email, but=['headers','att'])
    def send(self,
        thread_id:str=None,  # Thread id to reply in
        **kwargs
    ):
        "Send email (pass `to`, `subj`, `body` etc or an EmailMessage)"
        msg = mk_email(**kwargs)
        body = dict(raw=raw_msg(msg))
        if thread_id: body['threadId'] = thread_id
        res = self._exec(self._u.messages().send(userId=self.user_id,body=body))
        return Msg(self,d=res)

    @delegates(mk_email, but=['headers','att'])
    def create_draft(self,
        msg=None,            # EmailMessage (or use kwargs)
        thread_id:str=None,  # Thread id to reply in
        **kwargs
    ):  # Created draft
        "Create a draft (pass `to`, `subj`, `body` etc or an EmailMessage)"
        msg = ifnone(msg,mk_email(**kwargs))
        body = dict(message=dict(raw=raw_msg(msg)))
        if thread_id: body['message']['threadId'] = thread_id
        res = self._exec(self._u.drafts().create(userId=self.user_id,body=body))
        return Draft(self,d=res)

    def _reply_headers(self,m,to=None,subj=None,refs=None,in_reply_to=None):
        h = m.hdrs()
        to = ifnone(to,h.get('reply-to') or h.get('from'))
        subj = ifnone(subj,h.get('subject') or '')
        subj = subj if re.match(r'(?i)^re:',subj or '') else f'Re: {subj}'
        in_reply_to = ifnone(in_reply_to,h.get('message-id'))
        refs0 = h.get('references')
        refs = ifnone(refs,refs0)
        if refs and in_reply_to and in_reply_to not in refs: refs = f'{refs} {in_reply_to}'
        if not refs and in_reply_to: refs = in_reply_to
        return dict(to=to,subj=subj,refs=refs,in_reply_to=in_reply_to)

    @delegates(mk_email, but=['headers','att'])
    def reply_draft(self,
        o:str,                   # Message/Thread object or message id
        to:str=None,         # Override recipient
        subj:str=None,       # Override subject
        thread_id:str=None,  # Override thread id
        **kwargs
    ):
        "Create a reply draft to message/thread"
        if isinstance(o,Thread): o = o.last()
        if not isinstance(o,Msg): o = Msg(self,id=o)
        o.get(fmt='metadata')
        rh = self._reply_headers(o,to=to,subj=subj)
        h = {}
        if rh['in_reply_to']: h['In-Reply-To'] = rh['in_reply_to']
        if rh['refs']:        h['References'] = rh['refs']
        t_id = ifnone(thread_id,o.thread_id)
        msg = mk_email(to=rh['to'], subj=rh['subj'], headers=h, **kwargs)
        return self.create_draft(msg=msg,thread_id=t_id)

    def reply_to_thread(self,
        thread_id:str,       # Thread id to reply to
        body:str,            # Plain text body
        html:str=None,       # HTML body
        reply_all:bool=True  # Reply to all recipients?
    ):  # Created reply draft
        "Create a reply draft for a thread"
        t = self.thread(thread_id)
        m = t.last().get(fmt='metadata')
        h = m.hdrs()
        to = h.get('reply-to') or h.get('from', '')
        cc = None
        if reply_all:
            me = self.profile().email.lower()
            cc = {a.strip() for a in (h.get('to','')+','+h.get('cc','')).split(',')
                  if a.strip() and a.strip().lower() != me} - {to}
            cc = ','.join(cc) or None
        return t.reply_draft(body=body, html=html, to=to, cc=cc)

    def _batch_label(self, ids, add=None, rm=None, delay=0):
        if delay: time.sleep(delay)
        body = dict(ids=list(ids), addLabelIds=self.lbl_ids(add), removeLabelIds=self.lbl_ids(rm))
        return self._exec(self._u.messages().batchModify(userId=self.user_id, body=body))

    def batch_label(self,
        ids:list,         # Message ids (no limit)
        add:list=None,    # Label ids/names to add
        rm:list=None,     # Label ids/names to remove
        chunk_sz:int=999, # Chunk size (max 1000)
        delay:float=0.5   # Delay between chunks in seconds
    ):  # List of API responses
        "Batch modify labels on messages, auto-chunking"
        ids = _uniq(L(ids).map(_as_id))
        return [self._batch_label(b, add, rm, delay if i else 0)
                for i,b in enumerate(chunked(ids, chunk_sz))]

    def batch_delete(self,
        ids:list  # Message ids to delete permanently (max 1000)
    ):  # API response
        "Permanently delete messages (requires full mail scope)"
        ids = _uniq(L(ids).map(_as_id))
        body = dict(ids=ids)
        return self._exec(self._u.messages().batchDelete(userId=self.user_id,body=body))

    def trash_msgs(self,
        ids:list  # Message ids to trash
    ):  # List of trashed messages
        "Move messages to trash"
        return L(ids).map(_as_id).map(lambda i: self._exec(self._u.messages().trash(userId=self.user_id,id=i)))

    def report_spam(self,
        ids:list  # Message ids to report as spam
    ):
        "Report messages as spam"
        return self.batch_label(ids, add=['SPAM'], rm=['INBOX'])

    def _batch_get(self, items, cls, api, fmt='metadata', callback=None):
        import uuid
        results,id_map = {},{}
        def _cb(id, resp, exc):
            if exc: raise exc
            orig_id = id_map[id]
            results[orig_id] = cls(self, d=resp)
            if callback: callback(results[orig_id])
        batch = self.s.new_batch_http_request()
        for o in items:
            oid = o.id if hasattr(o, 'id') else o
            uid = f"{oid}_{uuid.uuid4().hex[:8]}"
            id_map[uid] = oid
            batch.add(api.get(userId=self.user_id, id=oid, format=fmt), callback=_cb, request_id=uid)
        batch.execute(http=self.s._http)
        return L(results[o.id if hasattr(o,'id') else o] for o in items)

    def send_drafts(self,
        ids: str|list[str] # id(s) of drafts to send
    ):
        "Send one or more drafts by id"
        return L(listify(ids)).map(lambda i: self.draft(i).send())

    def get_msgs(self, msgs, fmt='metadata', callback=None):
        "Batch fetch multiple messages"
        return self._batch_get(msgs, Msg, self._u.messages(), fmt, callback)

    def get_threads(self, threads, fmt='metadata', callback=None):
        "Batch fetch multiple threads"
        return self._batch_get(threads, Thread, self._u.threads(), fmt, callback)

    def view_inbox(self, max_msgs=20, unread=False):
        "Search and batch-fetch inbox messages"
        q = 'in:inbox is:unread' if unread else 'in:inbox'
        msgs = self.search_msgs(q, max_results=max_msgs)
        return self.get_msgs(msgs, fmt='full')

    def view_inbox_threads(self, max_threads=20, unread=False):
        "Search and batch-fetch inbox threads"
        q = 'in:inbox is:unread' if unread else 'in:inbox'
        threads = self.search_threads(q, max_results=max_threads)
        return self.get_threads(threads, fmt='full')

    def view_msgs(self,
        ids:list,            # Message ids to fetch
        fmt:str='metadata'   # Format: 'full', 'metadata', or 'minimal'
    ):
        "Batch fetch messages and return summary dicts"
        msgs = self.get_msgs(ids, fmt=fmt)
        return [{'id': m.id, 'thread_id': m.thread_id, 'frm': m.frm, 'to': m.to, 'subject': m.subj, 'snippet': m.snip} for m in msgs]

    def view_threads(self,
        ids:list,            # Thread ids to fetch
        fmt:str='metadata'   # Format: 'full', 'metadata', or 'minimal'
    ):
        "Batch fetch threads and return summary with message list"
        threads = self.get_threads(ids, fmt=fmt)
        return [{'id': t.id, 'msgs': [{'id': m.id, 'frm': m.frm, 'to': m.to, 'subject': m.subj,
                  'snippet': m.snip, 'labels': list(m.label_ids)} for m in t.msgs()]} for t in threads]

    def view_msg(self,
        id:str,              # Message id
        clean:bool=True,     # Strip reply quotations and signatures?
        as_text:bool=True,   # Return text body (vs HTML)?
        as_json:bool=True    # Return dict (vs formatted string)?
    ):
        "View message body with optional headers/metadata. This is primarily for LLM and programmatic use. Humans use `message()` to get HTML view."
        m = self.message(id, fmt='full')
        body = m.body(clean) if as_text else m.html(clean)
        h = m.hdrs()
        if not as_json:
            parts = [f"From: {h.get('from','')}", f"Date: {h.get('date','')}", f"To: {h.get('to','')}"]
            if h.get('cc'): parts.append(f"Cc: {h.get('cc')}")
            if h.get('bcc'): parts.append(f"Bcc: {h.get('bcc')}")
            parts.append(f"Subject: {h.get('subject','')}")
            return '\n'.join(parts) + '\n\n' + body
        return dict(id=m.id, thread_id=m.thread_id, frm=h.get('from'), to=h.get('to'),
                    cc=h.get('cc'), date=h.get('date'), subject=h.get('subject'), body=body)

    def view_thread(self,
        id:str,              # Thread id
        clean:bool=True,     # Strip reply quotations and signatures?
        as_text:bool=True,   # Return text body (vs HTML)?
        as_json:bool=True    # Return dict (vs formatted string)?
    ):
        "View thread messages with optional headers/metadata. This is primarily for LLM and programmatic use. Humans use `thread()` to get HTML view."
        t = self.thread(id, fmt='full')
        res = {m.id: self.view_msg(m.id, clean=clean, as_text=as_text, as_json=as_json) for m in t.msgs()}
        if as_json: return res
        return ('\n\n' + '='*60 + '\n\n').join(res.values())

