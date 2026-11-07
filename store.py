"""SQLite durability and best-effort loopback UDP wakeups without message payloads."""
import asyncio
from contextlib import contextmanager
import socket
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path, identity, peer):
        self.path, self.identity, self.peer = path, identity, peer
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, recipient TEXT NOT NULL,
                body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
            columns = {r['name'] for r in db.execute('PRAGMA table_info(messages)')}
            for name, declaration in [('thread_id', "TEXT NOT NULL DEFAULT ''"),
                                      ('reply_to', 'INTEGER'), ('client_token', 'TEXT'), ('read_at', 'TEXT')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE messages ADD COLUMN {name} {declaration}')
            db.execute('CREATE INDEX IF NOT EXISTS inbox_idx ON messages(recipient,id)')
            db.execute('CREATE INDEX IF NOT EXISTS thread_idx ON messages(thread_id,id)')
            db.execute('CREATE INDEX IF NOT EXISTS unread_idx ON messages(recipient,id) WHERE read_at IS NULL')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS retry_idx ON messages(sender,client_token) WHERE client_token IS NOT NULL')
            db.execute('CREATE TABLE IF NOT EXISTS presence (identity TEXT PRIMARY KEY,state TEXT,detail TEXT,expires REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS listeners (token TEXT PRIMARY KEY,port INTEGER,updated REAL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def send(self, message, thread, reply, token):
        if not message.strip() or len(message) > 20000:
            raise ValueError('Message must contain 1..20,000 characters and cannot be blank')
        if len(thread) > 100 or len(token) > 100 or reply < 0:
            raise ValueError('thread_id/client_token max 100 characters; reply_to >= 0')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if reply:
                parent = db.execute('SELECT * FROM messages WHERE id=? AND recipient=?', (reply, self.identity)).fetchone()
                if not parent:
                    raise ValueError('reply_to must reference an incoming message')
                if not thread:
                    thread = parent['thread_id']
                elif thread != parent['thread_id']:
                    raise ValueError('Reply thread must match the original message')
            if token:
                old = db.execute('SELECT * FROM messages WHERE sender=? AND client_token=?', (self.identity, token)).fetchone()
                if old:
                    if (old['body'], old['thread_id'], old['reply_to']) != (message, thread, reply or None):
                        raise ValueError('client_token already used for a different payload')
                    return {**dict(old), 'duplicate': True}
            cursor = db.execute('INSERT INTO messages(sender,recipient,body,thread_id,reply_to,client_token) VALUES (?,?,?,?,?,?)',
                                (self.identity, self.peer, message, thread, reply or None, token or None))
            row = db.execute('SELECT * FROM messages WHERE id=?', (cursor.lastrowid,)).fetchone()
        return {**dict(row), 'duplicate': False}

    def read(self, after, limit, thread='', history=False):
        where, values = 'id>?', [after]
        if not history:
            where += ' AND recipient=?'
            values.append(self.identity)
        if thread:
            where += ' AND thread_id=?'
            values.append(thread)
        with self.connect() as db:
            rows = db.execute(f'SELECT * FROM messages WHERE {where} ORDER BY id LIMIT ?', [*values, limit + 1]).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {'messages': [dict(row) for row in rows], 'next_after_id': rows[-1]['id'] if rows else after,
                'has_more': more, 'peer_status': self.peer_status()}

    def acknowledge(self, message_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM messages WHERE id=? AND recipient=?', (message_id, self.identity)).fetchone()
            if not row:
                raise ValueError('message_id must reference an incoming message')
            db.execute("UPDATE messages SET read_at=COALESCE(read_at,strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE id=?", (message_id,))
            return dict(db.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone())

    def set_status(self, state, detail, ttl):
        if state not in ('thinking', 'typing', 'working', 'waiting', 'idle') or not 5 <= ttl <= 300 or len(detail) > 300:
            raise ValueError('Use thinking/typing/working/waiting/idle, ttl_seconds 5..300, detail <= 300 chars')
        expires = time.time() + ttl
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO presence VALUES (?,?,?,?)', (self.identity, state, detail, expires))
        return {'identity': self.identity, 'state': state, 'detail': detail, 'expires_at': expires}

    def peer_status(self):
        with self.connect() as db:
            row = db.execute('SELECT * FROM presence WHERE identity=? AND expires>?', (self.peer, time.time())).fetchone()
        return dict(row) if row else {'identity': self.peer, 'state': 'unknown', 'detail': ''}

    def snapshot(self):
        with self.connect() as db:
            unread = db.execute('SELECT COUNT(*) FROM messages WHERE recipient=? AND read_at IS NULL', (self.identity,)).fetchone()[0]
            latest = db.execute('SELECT COALESCE(MAX(id),0) FROM messages WHERE recipient=?', (self.identity,)).fetchone()[0]
            receipts = db.execute('SELECT COUNT(*),COALESCE(MAX(id),0) FROM messages WHERE sender=? AND read_at IS NOT NULL', (self.identity,)).fetchone()
        return {'identity': self.identity, 'peer': self.peer, 'unread': unread,
                'latest_incoming_id': latest, 'latest_sent_message_acknowledged': receipts[1],
                'sent_acknowledged_count': receipts[0],
                'peer_status': self.peer_status()}


class Wakeup(asyncio.DatagramProtocol):
    def __init__(self, store, poll_only=False):
        self.store = store
        self.poll_only = poll_only
        self.event = asyncio.Event()
        self.transport = None
        self.token = uuid.uuid4().hex
        self.refresh_task = None

    async def start(self):
        if self.poll_only:
            return
        try:
            self.transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: self, local_addr=('127.0.0.1', 0), family=socket.AF_INET)
            self.register()
            self.refresh_task = asyncio.create_task(self.refresh())
        except OSError:
            if self.transport:
                self.transport.close()
            self.transport = None

    def register(self):
        with self.store.connect() as db:
            db.execute('DELETE FROM listeners WHERE updated<?', (time.time() - 3600,))
            db.execute('INSERT OR REPLACE INTO listeners VALUES (?,?,?)',
                       (self.token, self.transport.get_extra_info('sockname')[1], time.time()))

    async def refresh(self):
        while True:
            await asyncio.sleep(300)
            self.register()

    def datagram_received(self, data, address):
        if data == b'change' and address[0] == '127.0.0.1':
            self.pulse()

    def pulse(self):
        previous, self.event = self.event, asyncio.Event()
        previous.set()

    def signal(self):
        self.pulse()
        if self.transport:
            with self.store.connect() as db:
                ports = [row[0] for row in db.execute('SELECT port FROM listeners WHERE token!=? AND updated>?', (self.token, time.time() - 3600))]
            for port in ports:
                try:
                    self.transport.sendto(b'change', ('127.0.0.1', port))
                except OSError:
                    pass

    async def wait(self, event, timeout):
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    async def stop(self):
        if self.refresh_task:
            self.refresh_task.cancel()
            await asyncio.gather(self.refresh_task, return_exceptions=True)
        if self.transport:
            self.transport.close()
            with self.store.connect() as db:
                db.execute('DELETE FROM listeners WHERE token=?', (self.token,))
