import time,uuid,pytest
from contextlib import ExitStack
from solvemail import Thread

def _poll(f,cond,max_wait=30,slp=1):
    t0 = time.time()
    while True:
        o = f()
        if cond(o): return o
        if time.time()-t0>max_wait: pytest.fail(f'Timed out after {max_wait}s waiting for Gmail')
        time.sleep(slp)

@pytest.mark.timeout(120)
def test_gmail_conversation(g):
    me = g.profile().email
    uid = uuid.uuid4().hex[:10]
    subj = f'solvemail e2e {uid}'
    unsub_subj = f'unsubscribe-{uid}'
    with ExitStack() as cleanup:
        lbl = g.create_label(f'solvemail-e2e-thread-{uid}')
        cleanup.callback(lbl.delete)
        assert g.label(lbl.name).id == lbl.id
        assert lbl.id in [o.id for o in g.find_labels(uid)]
        lbl.rename(lbl.name+'-renamed')
        assert g.label(lbl.name).id == lbl.id
        data = b'hello solvemail\x00\xff'
        att = [('att.bin',data,'application/octet-stream')]
        m = g.send(to=me,subj=subj,body='hello',att=att,headers={'List-Unsubscribe': f'<mailto:{me}?subject={unsub_subj}>'})
        cleanup.callback(Thread(g,id=m.thread_id).trash)
        m = _poll(lambda: g.email(m.id,fmt='full'),lambda o: bool(o.d.get('payload')),max_wait=20)
        assert (m.to,m.subj) == (me,subj)
        assert m.text().strip() == 'hello'
        assert m.att(0) == data

        t = Thread(g,id=m.thread_id)
        t.add_labels(lbl)
        t = g.thread(t.id,fmt='metadata')
        emails = t.emails()
        assert emails and all(lbl.id in o.label_ids for o in emails)

        n0 = len(emails)
        d = t.reply_draft(body='reply')
        sent = d.send()
        emails = _poll(lambda: g.thread(t.id,fmt='metadata').emails(),lambda o: len(o)>n0)
        assert sent.thread_id == t.id and sent.id in [o.id for o in emails]

        unsub = m.unsubscribe()
        cleanup.callback(unsub.trash)
        unsub = _poll(lambda: g.email(unsub.id,fmt='full'),lambda o: bool(o.d.get('payload')),max_wait=20)
        assert unsub.to == me
        assert unsub.subj == unsub_subj
        assert unsub.text().strip() == 'unsubscribe'
