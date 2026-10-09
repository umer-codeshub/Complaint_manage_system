import base64
from email import message_from_bytes
import pytest
from tools.gmail_sender import prepare_message, send_email, GmailAuthError, GmailUnknownError

class HttpLike(Exception):
    def __init__(self,status): self.resp=type('Resp',(),{'status':status})()
class Service:
    def __init__(self, msgid='gmail_msg_mock_01', fail=None):
        self.msgid=msgid; self.fail=fail; self.calls=0; self.request=None
    def users(self): return self
    def messages(self): return self
    def send(self, userId, body):
        assert userId=='me'
        self.request=body; self.calls+=1
        return self
    def execute(self):
        if self.fail: raise self.fail
        return {'id':self.msgid}

def test_mime_message_encoding():
    r=prepare_message('a@example.com','Demo Subject','Hello there')
    msg=message_from_bytes(base64.urlsafe_b64decode(r['raw']))
    assert msg['To']=='a@example.com' and msg['Subject']=='Demo Subject'

def test_invalid_recipient_rejected():
    with pytest.raises(ValueError): prepare_message('a@example.com\nBcc: bad@evil.test','Hi','Body')

def test_success_returns_gmail_message_id(credentials):
    service=Service()
    assert send_email('a@example.com','Subject','Body',credentials,service_factory=lambda _:service)==service.msgid
    assert service.calls==1

def test_auth_expired_requires_reconnect(credentials):
    credentials.valid=False; credentials.expired=True
    with pytest.raises(GmailAuthError): send_email('a@example.com','Subject','Body',credentials,service_factory=lambda _:Service())

def test_gmail_auth_error(credentials):
    with pytest.raises(GmailAuthError):
        send_email('a@example.com','Subject','Body',credentials,service_factory=lambda _:Service(fail=HttpLike(401)))

def test_gmail_permission_error(credentials):
    with pytest.raises(GmailAuthError):
        send_email('a@example.com','Subject','Body',credentials,service_factory=lambda _:Service(fail=HttpLike(403)))

def test_gmail_server_error_is_unknown(credentials):
    with pytest.raises(GmailUnknownError):
        send_email('a@example.com','Subject','Body',credentials,service_factory=lambda _:Service(fail=HttpLike(503)))
