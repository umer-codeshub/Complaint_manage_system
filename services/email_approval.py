"""At-most-one application send attempt per ticket. UNKNOWN requires manual reconciliation."""
from tools.gmail_sender import GmailAuthError, GmailUnknownError, prepare_message, send_email
from tools.ticket_generator import TicketStore, TicketError, utcnow

class ApprovalError(Exception):
    pass

def approval_is_valid(gmail_connected, recipient, subject, body, approved, test_recipient_confirmed,
                      registered_email):
    try:
        prepare_message(recipient, subject, body)
    except ValueError:
        return False
    return bool(gmail_connected and approved and
                (recipient.casefold() == registered_email.casefold() or test_recipient_confirmed))

def approve_and_send(store: TicketStore, ticket_id: str, recipient: str, subject: str, body: str,
                     approved: bool, credentials, test_recipient_confirmed: bool = False,
                     send_func=send_email):
    # Every condition is checked again server-side, not only in UI.
    original = store.get(ticket_id)
    if not approval_is_valid(credentials is not None, recipient, subject, body, approved,
                             test_recipient_confirmed, original['customer_email']):
        raise ApprovalError('Approval, connection, or email details are invalid')
    def reserve(t):
        if t['email_status'] != 'DRAFT':
            raise ApprovalError('Ticket already has a send attempt; duplicates are blocked')
        t.update(email_status='SENDING', email_approval_status='Approved', email_recipient=recipient,
                 email_subject=subject, customer_reply_draft=body)
        return t
    store.update(ticket_id, reserve)  # Persist intent before external side effect.
    try:
        msg_id = send_func(recipient, subject, body, credentials)
    except GmailAuthError:
        # Authentication errors cannot represent a successful request to Gmail.
        store.update(ticket_id, lambda t: {**t, 'email_status': 'DRAFT',
                                           'email_approval_status': 'Pending'})
        raise
    except Exception as exc:
        # Network uncertainty: no automatic retry; manual inspection first.
        store.update(ticket_id, lambda t: {**t, 'email_status': 'UNKNOWN',
                                           'ticket_status': 'Manual Gmail reconciliation needed'})
        raise GmailUnknownError('Send outcome unknown. Check Gmail Sent; do not press Send again.') from exc
    return store.update(ticket_id, lambda t: {**t, 'email_status': 'SUBMITTED',
                'gmail_message_id': msg_id, 'submitted_at': utcnow(),
                'ticket_status': 'Email Submitted'})
