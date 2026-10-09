from tools.ticket_generator import TicketStore, TicketError

def payload():
    return {'decision':{'escalated':False}, 'customer_email':'ayesha@example.com',
            'category':'late_delivery','priority':'Medium','email_subject':'Update','customer_reply_draft':'Draft'}

def test_two_tickets_have_unique_ids(store):
    a=store.create(payload()); b=store.create(payload())
    assert a['ticket_id'] != b['ticket_id']
    assert store.get(a['ticket_id'])['email_status'] == 'DRAFT'

def test_safe_atomic_ticket_update(store):
    t=store.create(payload())
    store.update(t['ticket_id'],lambda value:{**value,'ticket_status':'Manual review'})
    assert store.get(t['ticket_id'])['ticket_status']=='Manual review'

def test_ticket_path_traversal_rejected(store):
    try:
        store.get('../../app.py')
    except TicketError:
        pass
    else:
        assert False
