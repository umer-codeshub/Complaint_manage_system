import pytest
from services.email_approval import approve_and_send, ApprovalError, approval_is_valid
from tools.gmail_sender import GmailUnknownError

def ticket(store):
    return store.create({'decision':{'escalated':False},'customer_email':'ayesha@example.com',
                         'category':'late_delivery','priority':'Medium','email_subject':'Your order',
                         'customer_reply_draft':'Customer email reply draft.'})

def test_approval_checkbox_required(store, credentials):
    t=ticket(store)
    with pytest.raises(ApprovalError):
        approve_and_send(store,t['ticket_id'],'ayesha@example.com','Your order','This is the body',False,credentials)
    assert store.get(t['ticket_id'])['email_status']=='DRAFT'

def test_no_gmail_connection_blocks_send(store):
    t=ticket(store)
    with pytest.raises(ApprovalError):
        approve_and_send(store,t['ticket_id'],'ayesha@example.com','Your order','This is the body',True,None)

def test_unconfirmed_alternate_email_blocked(store,credentials):
    t=ticket(store)
    with pytest.raises(ApprovalError):
        approve_and_send(store,t['ticket_id'],'test@myemail.org','Your order','This is the body',True,credentials)

def test_explicit_test_recipient_can_send(store,credentials):
    t=ticket(store)
    result=approve_and_send(store,t['ticket_id'],'test@myemail.org','Your order','This is the body',True,
                            credentials,True,send_func=lambda *args:'id123')
    assert result['email_status']=='SUBMITTED' and result['email_recipient']=='test@myemail.org'

def test_submission_updates_ticket_and_blocks_duplicates(store,credentials):
    t=ticket(store); calls=[]
    def mock_send(*args): calls.append(1);return 'mock-123'
    result=approve_and_send(store,t['ticket_id'],'ayesha@example.com','Your order','This is the body',True,
                            credentials,send_func=mock_send)
    assert result['gmail_message_id']=='mock-123'
    assert result['submitted_at'] and result['ticket_status']=='Email Submitted'
    with pytest.raises(ApprovalError):
        approve_and_send(store,t['ticket_id'],'ayesha@example.com','Your order','This is the body',True,
                         credentials,send_func=mock_send)
    assert len(calls)==1

def test_uncertain_send_stays_blocked_and_no_false_success(store,credentials):
    t=ticket(store)
    with pytest.raises(GmailUnknownError):
        approve_and_send(store,t['ticket_id'],'ayesha@example.com','Your order','This is the body',True,
                          credentials,send_func=lambda *a: (_ for _ in ()).throw(OSError('network')))
    updated=store.get(t['ticket_id'])
    assert updated['email_status']=='UNKNOWN' and updated['gmail_message_id'] is None
    assert updated['ticket_status']=='Manual Gmail reconciliation needed'

def test_disabled_before_valid_approval():
    assert not approval_is_valid(True,'a@example.com','Subject','Body',False,False,'a@example.com')
