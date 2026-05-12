import time,uuid,pytest
from fastcore.test import test_eq as eq, test as check

def _poll(f,cond,max_wait=30,slp=1):
    t0 = time.time()
    while True:
        o = f()
        if cond(o): return o
        if time.time()-t0>max_wait: return o
        time.sleep(slp)

@pytest.mark.timeout(120)
def test_labels(g):
    uid = uuid.uuid4().hex[:10]
    nm = f'solvemail-e2e-{uid}'
    lbl = g.create_label(nm)
    try:
        eq(g.label(nm).id,lbl.id)
        check(lbl.id in [o.id for o in g.find_labels(uid)])
        lbl.rename(nm+'-renamed')
        eq(g.label(nm+'-renamed').id,lbl.id)
    finally:
        try: lbl.delete()
        except Exception: pass

@pytest.mark.timeout(120)
def test_send_reply_draft_and_attachments(g):
    me = g.profile().email
    uid = uuid.uuid4().hex[:10]
    subj = f'solvemail e2e {uid}'
    lbl = g.create_label(f'solvemail-e2e-thread-{uid}')
    m = None
    try:
        att = [('att.txt',b'hello solvemail','text/plain')]
        m = g.send(to=me,subj=subj,body='hello',att=att)
        m = _poll(lambda: g.email(m.id,fmt='full'),lambda o: bool(o.d.get('payload')),max_wait=20)
        aps = m.att_parts()
        check(len(aps)>0)
        eq(m.att(0),b'hello solvemail')

        t = g.thread(m.thread_id,fmt='metadata')
        t.add_labels(lbl)
        t = g.thread(t.id,fmt='metadata')
        check(all(lbl.id in o.d.get('labelIds',[]) for o in t.emails()))

        n0 = len(g.thread(t.id,fmt='metadata').emails())
        d = t.reply_draft(body='reply')
        sent = d.send()
        _poll(lambda: len(g.thread(t.id,fmt='metadata').emails()),lambda n: n>n0,max_wait=30)
        check(sent.thread_id==t.id)
    finally:
        try:
            if m: g.thread(m.thread_id).trash()
        except Exception: pass
        try: lbl.delete()
        except Exception: pass
