"""Atomic JSON ticket store with cross-worker file locking (ephemeral demo storage)."""
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from filelock import FileLock

TICKET_ID_RE = re.compile(r'^TKT-[0-9a-f]{32}$')

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

class TicketError(Exception):
    pass

class TicketStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.directory / '.tickets.lock'), timeout=10)

    def _path(self, ticket_id: str) -> Path:
        if not TICKET_ID_RE.fullmatch(ticket_id):
            raise TicketError('Invalid ticket ID')
        return self.directory / f'{ticket_id}.json'

    @staticmethod
    def _write(path: Path, data: dict):
        fd, tmp = tempfile.mkstemp(prefix='.pending-', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                os.chmod(tmp, 0o600)
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def create(self, payload: dict) -> dict:
        ticket = {**payload, 'ticket_id': f'TKT-{uuid4().hex}',
                  'created_at': utcnow(), 'updated_at': utcnow(),
                  'ticket_status': 'Needs human review' if payload['decision']['escalated'] else 'Open',
                  'email_approval_status': 'Pending', 'email_status': 'DRAFT',
                  'gmail_message_id': None, 'submitted_at': None}
        with self.lock:
            path = self._path(ticket['ticket_id'])
            if path.exists():
                raise TicketError('Ticket ID collision')
            self._write(path, ticket)
        return ticket

    def get(self, ticket_id: str) -> dict:
        with self.lock:
            try:
                return json.loads(self._path(ticket_id).read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                raise TicketError('Ticket not available') from exc

    def update(self, ticket_id: str, update_fn):
        with self.lock:
            path = self._path(ticket_id)
            try:
                existing = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                raise TicketError('Ticket not available') from exc
            revised = update_fn(dict(existing))
            if revised['ticket_id'] != ticket_id:
                raise TicketError('Ticket ID cannot change')
            revised['updated_at'] = utcnow()
            self._write(path, revised)
            return revised

    def list_recent(self, limit=25):
        entries = []
        with self.lock:
            for p in self.directory.glob('TKT-*.json'):
                try:
                    item = json.loads(p.read_text(encoding='utf-8'))
                    entries.append({k: item.get(k) for k in ('ticket_id','created_at','ticket_status','email_status','category','priority')})
                except (OSError, json.JSONDecodeError):
                    continue
        return sorted(entries, key=lambda x: x.get('created_at') or '', reverse=True)[:limit]
