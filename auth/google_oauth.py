"""Single-operator Google OAuth web flow with persisted one-use signed CSRF state.

State survives Streamlit OAuth full-page redirects; credentials never go to disk.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse
from filelock import FileLock

GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
TTL_SECONDS = 600

class OAuthSetupError(Exception):
    pass

class OAuthStateError(Exception):
    pass


def validate_settings(client_id, client_secret, redirect_uri, state_secret):
    if not all((client_id, client_secret, redirect_uri, state_secret)):
        raise OAuthSetupError('Missing Google OAuth configuration or state signing secret')
    parsed = urlparse(redirect_uri)
    if (not parsed.netloc or parsed.fragment or parsed.query or parsed.username or parsed.password
        or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1')))):
        raise OAuthSetupError('OAuth redirect must be an exact HTTPS URL (or HTTP localhost) without query parameters')
    if len(state_secret) < 32:
        raise OAuthSetupError('OAUTH_STATE_SECRET must be at least 32 characters')


def _flow(client_id, client_secret, redirect_uri, state=None):
    config = {'web': {'client_id': client_id, 'client_secret': client_secret,
              'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
              'token_uri': 'https://oauth2.googleapis.com/token',
              'redirect_uris': [redirect_uri]}}
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(config, scopes=[GMAIL_SCOPE], redirect_uri=redirect_uri, state=state)


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def _unb64(encoded):
    return base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))


def make_state(secret, now=None):
    created = int(now if now is not None else time.time())
    payload = f'{created}.{secrets.token_urlsafe(24)}'
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64(payload.encode()) + '.' + _b64(sig)


def verify_state(state, secret, now=None):
    try:
        encoded, encoded_mac = state.split('.')
        payload = _unb64(encoded).decode()
        issued_text, nonce = payload.split('.', 1)
        issued = int(issued_text)
        supplied = _unb64(encoded_mac)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
        current = int(now if now is not None else time.time())
        if (not hmac.compare_digest(expected, supplied) or not nonce or
            issued > current + 30 or current - issued > TTL_SECONDS):
            raise ValueError('Expired or invalid')
        return hashlib.sha256(state.encode()).hexdigest()
    except (ValueError, TypeError, AttributeError, UnicodeError) as exc:
        raise OAuthStateError('OAuth state was invalid or expired; reconnect Gmail') from exc


class PendingStates:
    """One-use nonce registry in ephemeral storage. No raw authorization tokens stored."""
    def __init__(self, root: Path):
        self.path = Path(root) / '.oauth_pending.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + '.lock')

    def _read(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _save(self, entries):
        # File contains only nonce digests and expiry timestamps.
        from tools.ticket_generator import TicketStore
        TicketStore._write(self.path, entries)

    def add(self, digest, now=None):
        with self.lock:
            entries = {k: v for k, v in self._read().items() if v >= (now or time.time())}
            entries[digest] = (now or time.time()) + TTL_SECONDS
            self._save(entries)

    def consume(self, digest, now=None):
        with self.lock:
            entries = self._read()
            expiration = entries.pop(digest, None)
            self._save(entries)
            if expiration is None or expiration < (now or time.time()):
                raise OAuthStateError('OAuth state not recognized, expired or already used')


def begin_oauth(client_id, client_secret, redirect_uri, state_secret, registry):
    validate_settings(client_id, client_secret, redirect_uri, state_secret)
    state = make_state(state_secret)
    registry.add(verify_state(state, state_secret))
    flow = _flow(client_id, client_secret, redirect_uri)
    url, _ = flow.authorization_url(access_type='offline', prompt='consent', state=state,
                                   include_granted_scopes='false')
    return url


def complete_oauth(client_id, client_secret, redirect_uri, state_secret, registry, state, code):
    validate_settings(client_id, client_secret, redirect_uri, state_secret)
    if not isinstance(code, str) or not code.strip() or len(code) > 3000:
        raise OAuthStateError('Google authorization code missing')
    digest = verify_state(state, state_secret)
    registry.consume(digest)  # consume before any token request, including failed attempts
    flow = _flow(client_id, client_secret, redirect_uri, state=state)
    flow.fetch_token(code=code)
    return flow.credentials
