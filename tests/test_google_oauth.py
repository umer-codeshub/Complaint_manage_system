import pytest
from auth.google_oauth import (make_state, verify_state, PendingStates, OAuthStateError,
                               OAuthSetupError, validate_settings, begin_oauth, complete_oauth)

def settings():
    return ['cid','csecret','https://complaintmanagesystem-2v.streamlit.app/', 's'*64]

def test_missing_client_id():
    args=settings();args[0]=''
    with pytest.raises(OAuthSetupError): validate_settings(*args)

def test_invalid_redirect_url():
    args=settings(); args[2]='http://attacker.example/callback'
    with pytest.raises(OAuthSetupError): validate_settings(*args)

def test_signed_oauth_state_and_expiry():
    state=make_state('s'*64,now=1000)
    assert len(verify_state(state,'s'*64,now=1005))==64
    with pytest.raises(OAuthStateError): verify_state(state,'s'*64,now=1800)

def test_tampered_oauth_state():
    state=make_state('s'*64,now=1000)
    with pytest.raises(OAuthStateError): verify_state(state[:-4]+'ABCD','s'*64,now=1005)

def test_pending_state_consumed_once(tmp_path):
    r=PendingStates(tmp_path);r.add('abc',now=1000)
    r.consume('abc',now=1001)
    with pytest.raises(OAuthStateError): r.consume('abc',now=1002)

def test_complete_oauth_uses_registered_state(tmp_path, monkeypatch):
    import auth.google_oauth as module
    class FakeFlow:
        credentials='in-memory_mock_credentials'
        def authorization_url(self, **kw):return ('https://accounts.google.com/o/oauth2/auth?state=test',kw['state'])
        def fetch_token(self,**kw): assert kw['code']=='mock-code'
    monkeypatch.setattr(module,'_flow',lambda *a, **k:FakeFlow())
    r=PendingStates(tmp_path)
    # Authorization URL generation and callback would use the same issued state in actual OAuth.
    _, _, url, secret = settings()
    begin_oauth('cid','secret',url,secret,r)
    state=make_state(secret)
    r.add(verify_state(state,secret))
    assert complete_oauth('cid','secret',url,secret,r,state,'mock-code')=='in-memory_mock_credentials'
    with pytest.raises(OAuthStateError):complete_oauth('cid','secret',url,secret,r,state,'mock-code')
