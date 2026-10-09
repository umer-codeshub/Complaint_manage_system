"""Official Gmail API sender; no SMTP credentials and no automatic sends."""
import base64
import re
from email.message import EmailMessage
from email.utils import parseaddr

class GmailSendError(Exception):
    pass

class GmailAuthError(GmailSendError):
    pass

class GmailUnknownError(GmailSendError):
    """A request may have succeeded despite the client receiving an error."""


def validate_recipient(address: str) -> str:
    if not isinstance(address, str) or '\r' in address or '\n' in address:
        raise ValueError('Invalid recipient email')
    name, value = parseaddr(address)
    if name or value != address or not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', value):
        raise ValueError('Invalid recipient email')
    return value

def prepare_message(recipient: str, subject: str, body: str) -> dict:
    validate_recipient(recipient)
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 150 or any(c in subject for c in '\r\n'):
        raise ValueError('Invalid subject')
    if not isinstance(body, str) or not body.strip() or len(body) > 5000:
        raise ValueError('Invalid body')
    message = EmailMessage()
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')}

def send_email(recipient: str, subject: str, body: str, credentials, service_factory=None) -> str:
    payload = prepare_message(recipient, subject, body)  # no outgoing request so far
    if credentials is None:
        raise GmailAuthError('Gmail is not connected')
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
            except Exception as exc:
                raise GmailAuthError('Gmail authorization expired; reconnect your account') from exc
        else:
            raise GmailAuthError('Gmail authorization expired; reconnect your account')
    try:
        if service_factory:
            service = service_factory(credentials)
        else:
            from googleapiclient.discovery import build
            service = build('gmail','v1',credentials=credentials, cache_discovery=False)
        result = service.users().messages().send(userId='me', body=payload).execute()
        message_id = result.get('id')
        if not message_id or not isinstance(message_id, str):
            raise GmailUnknownError('Gmail response did not include a message ID; check Sent manually')
        return message_id
    except GmailUnknownError:
        raise
    except Exception as exc:
        # HttpError from googleapiclient carries .resp.status. Avoid importing the SDK
        # during offline/mock testing (it is required for deployed live sending).
        status = getattr(getattr(exc, 'resp', None), 'status', None)
        if status in (401, 403):
            raise GmailAuthError('Gmail rejected authorization or permission; reconnect or check scope') from exc
        raise GmailUnknownError('Gmail outcome uncertain; inspect Gmail Sent before retrying') from exc
