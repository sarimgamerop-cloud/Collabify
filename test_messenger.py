"""Real stdio clients; standard-library-only integration tests and latency measurement."""
import json
from contextlib import closing
from pathlib import Path
import queue
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from store import Store

ROOT = Path(__file__).resolve().parent


class Client:
    def __init__(self, identity, db, poll_only=False):
        command = [sys.executable, str(ROOT / 'server.py'), '--identity', identity, '--db', str(db)]
        if poll_only:
            command.append('--poll-only')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.responses, self.notifications, self.errors = queue.Queue(), [], []
        self.saved = {}
        self.counter = 0
        self.reader = threading.Thread(target=self.pump, daemon=True)
        self.reader.start()
        result = self.call('initialize', {'protocolVersion': '2025-11-25'})
        assert result['serverInfo']['version'] == '2.0.0'
        self.notify('notifications/initialized')

    def pump(self):
        for line in self.process.stdout:
            try:
                value = json.loads(line)
                if 'id' in value:
                    self.responses.put(value)
                else:
                    self.notifications.append(value)
            except Exception as exc:
                self.errors.append(str(exc))

    def write(self, value):
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def notify(self, method, params=None):
        self.write({'jsonrpc': '2.0', 'method': method, 'params': params or {}})

    def send(self, method, params=None):
        self.counter += 1
        self.write({'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params or {}})
        return self.counter

    def receive(self, request_id, timeout=6):
        deadline = time.monotonic() + timeout
        while request_id not in self.saved:
            value = self.responses.get(timeout=max(0.01, deadline - time.monotonic()))
            self.saved[value['id']] = value
        return self.saved.pop(request_id)

    def call(self, method, params=None):
        result = self.receive(self.send(method, params))
        assert 'error' not in result, result
        return result['result']

    def tool(self, name, **arguments):
        result = self.call('tools/call', {'name': name, 'arguments': arguments})
        assert not result['isError'], result
        return json.loads(result['content'][0]['text'])

    def pending_tool(self, name, **arguments):
        return self.send('tools/call', {'name': name, 'arguments': arguments})

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=4)
                raise AssertionError('Server did not stop promptly on EOF')
        self.reader.join(timeout=2)
        error = self.process.stderr.read()
        self.process.stdout.close()
        self.process.stderr.close()
        assert self.process.returncode == 0, error
        assert not self.errors, self.errors


class MessengerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / 'messages.sqlite3'
        self.clients = []
        self.a = self.client('ai-a')
        self.b = self.client('ai-b')

    def client(self, identity, poll_only=False):
        client = Client(identity, self.db, poll_only)
        self.clients.append(client)
        return client

    def tearDown(self):
        try:
            for client in self.clients:
                client.close()
        finally:
            self.directory.cleanup()

    def test_exchange_receipts_threads_and_dedup(self):
        self.assertEqual(len(self.a.call('tools/list')['tools']), 9)
        sent = self.a.tool('send_message', message='Hi B! \U0001f44b', thread_id='design', client_token='one')
        duplicate = self.a.tool('send_message', message='Hi B! \U0001f44b', thread_id='design', client_token='one')
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(sent['id'], duplicate['id'])
        self.assertEqual(self.b.tool('get_status')['unread'], 1)
        incoming = self.b.tool('read_messages', thread_id='design')
        self.assertEqual(incoming['messages'][0]['body'], 'Hi B! \U0001f44b')
        self.assertEqual(self.b.tool('read_messages', after_id=incoming['next_after_id'])['messages'], [])
        ack = self.b.tool('acknowledge', message_id=sent['id'])
        self.assertEqual(self.b.tool('acknowledge', message_id=sent['id'])['read_at'], ack['read_at'])
        self.assertEqual(self.b.tool('get_status')['unread'], 0)
        self.assertEqual(self.a.tool('get_status')['latest_sent_message_acknowledged'], sent['id'])
        response = self.b.tool('exchange', message='Hi A!', reply_to=sent['id'], after_id=sent['id'], wait_seconds=0)
        self.assertEqual(response['sent']['thread_id'], 'design')
        self.assertEqual(self.a.tool('read_messages')['messages'][0]['reply_to'], sent['id'])
        self.assertEqual(len(self.a.tool('conversation', thread_id='design')['messages']), 2)

    def test_validation_and_pagination(self):
        for arguments in ({'message': ''}, {'message': 'x', 'reply_to': 999},
                          {'message': 'x', 'sender': 'ai-b'}, {'message': 3}):
            self.assertTrue(self.a.call('tools/call', {'name': 'send_message', 'arguments': arguments})['isError'])
        self.a.tool('send_message', message='first', client_token='key')
        self.assertTrue(self.a.call('tools/call', {'name': 'send_message', 'arguments': {'message': 'different', 'client_token': 'key'}})['isError'])
        for _ in range(3):
            self.a.tool('send_message', message='next')
        page = self.b.tool('read_messages', limit=2)
        self.assertTrue(page['has_more'])
        page2 = self.b.tool('read_messages', after_id=page['next_after_id'], limit=2)
        self.assertFalse(page2['has_more'])
        self.assertEqual(len(page2['messages']), 2)
        self.assertTrue(self.a.call('tools/call', {'name': 'acknowledge', 'arguments': {'message_id': 1}})['isError'])
        unknown = self.a.receive(self.a.send('tools/call', {'name': 'missing'}))
        self.assertEqual(unknown['error']['code'], -32602)

    def test_out_of_order_receipts(self):
        first = self.a.tool('send_message', message='first')
        second = self.a.tool('send_message', message='second')
        self.b.tool('acknowledge', message_id=second['id'])
        before = self.a.tool('get_status')
        self.b.tool('acknowledge', message_id=first['id'])
        after = self.a.tool('get_status')
        self.assertEqual(before['latest_sent_message_acknowledged'], after['latest_sent_message_acknowledged'])
        self.assertEqual(before['sent_acknowledged_count'], 1)
        self.assertEqual(after['sent_acknowledged_count'], 2)

    def test_simultaneous_exchange_and_cancelled_send_retry(self):
        first = self.a.pending_tool('exchange', message='Plan A', thread_id='simultaneous',
                                    wait_seconds=10, client_token='sim-a')
        second = self.b.pending_tool('exchange', message='Plan B', thread_id='simultaneous',
                                     wait_seconds=10, client_token='sim-b')
        a_result = json.loads(self.a.receive(first)['result']['content'][0]['text'])
        b_result = json.loads(self.b.receive(second)['result']['content'][0]['text'])
        self.assertEqual(a_result['messages'][0]['body'], 'Plan B')
        self.assertEqual(b_result['messages'][0]['body'], 'Plan A')
        pending = self.a.pending_tool('exchange', message='Committed before cancellation',
                                      after_id=a_result['next_after_id'], wait_seconds=30,
                                      client_token='cancel-retry')
        self.a.call('ping')
        self.a.notify('notifications/cancelled', {'requestId': pending})
        self.a.call('ping')
        retried = self.a.tool('exchange', message='Committed before cancellation',
                              after_id=a_result['next_after_id'], wait_seconds=0,
                              client_token='cancel-retry')
        self.assertTrue(retried['sent']['duplicate'])
        history = self.b.tool('conversation')['messages']
        self.assertEqual(sum(row['body'] == 'Committed before cancellation' for row in history), 1)

    def test_protocol_errors_and_resource_discovery(self):
        resources = self.a.call('resources/list')['resources']
        self.assertEqual(resources[0]['uri'], 'messenger://inbox/ai-a')
        self.assertEqual(self.a.call('resources/templates/list'), {'resourceTemplates': []})
        bad = self.a.receive(self.a.send('resources/read', {'uri': 'messenger://inbox/ai-b'}))
        self.assertEqual(bad['error']['code'], -32002)
        bad = self.a.receive(self.a.send('unknown/method'))
        self.assertEqual(bad['error']['code'], -32601)
        self.a.process.stdin.write('{bad-json\n')
        self.a.process.stdin.flush()
        self.assertEqual(self.a.receive(None)['error']['code'], -32700)
        self.a.write([])
        self.assertEqual(self.a.receive(None)['error']['code'], -32600)
        self.assertEqual(self.a.call('ping'), {})

    def test_status_activity_subscription_and_cancel(self):
        uri = 'messenger://inbox/ai-b'
        self.b.call('resources/subscribe', {'uri': uri})
        request = self.b.pending_tool('wait_for_activity', wait_seconds=10)
        self.b.call('ping')  # Proves the wait doesn't block subsequent RPC requests.
        self.a.tool('set_status', state='typing', detail='Preparing an answer')
        response = self.b.receive(request)
        result = json.loads(response['result']['content'][0]['text'])
        self.assertEqual(result['event'], 'status_or_receipt')
        deadline = time.monotonic() + 4
        while not self.b.notifications and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(any(n['method'] == 'notifications/resources/updated' for n in self.b.notifications))
        resource = self.b.call('resources/read', {'uri': uri})
        self.assertEqual(json.loads(resource['contents'][0]['text'])['peer_status']['state'], 'typing')
        self.b.call('resources/unsubscribe', {'uri': uri})
        pending = self.b.pending_tool('read_messages', wait_seconds=30)
        self.b.call('ping')
        self.b.notify('notifications/cancelled', {'requestId': pending})
        self.b.call('ping')
        self.a.tool('send_message', message='After cancellation')
        self.assertEqual(len(self.b.tool('read_messages')['messages']), 1)
        self.assertNotIn(pending, self.b.saved)

    def test_persistence_and_expired_status(self):
        self.a.tool('send_message', message='Persist me')
        self.b.close()
        self.clients.remove(self.b)
        self.b = self.client('ai-b')
        self.assertEqual(self.b.tool('read_messages')['messages'][0]['body'], 'Persist me')
        store = Store(self.db, 'ai-a', 'ai-b')
        with patch('store.time.time', return_value=100):
            store.set_status('working', '', 5)
        self.assertEqual(self.b.tool('get_status')['peer_status']['state'], 'unknown')

    def test_wake_latency(self):
        samples, cursor = [], 0
        for index in range(20):
            pending = self.b.pending_tool('read_messages', after_id=cursor, wait_seconds=10)
            self.b.call('ping')
            started = time.perf_counter()
            self.a.tool('send_message', message=f'latency-{index}')
            response = self.b.receive(pending)
            samples.append((time.perf_counter() - started) * 1000)
            cursor = json.loads(response['result']['content'][0]['text'])['next_after_id']
        with closing(sqlite3.connect(self.db)) as db:
            fast_path = db.execute('SELECT COUNT(*) FROM listeners').fetchone()[0] == 2
        p95 = sorted(samples)[18]
        print(f'\nDelivery ({"UDP wake" if fast_path else "fallback"}, 20 samples): median={statistics.median(samples):.1f}ms p95={p95:.1f}ms max={max(samples):.1f}ms', flush=True)
        self.assertLess(max(samples), 3000)

    def test_socketless_fallback_and_eof(self):
        self.b.close()
        self.clients.remove(self.b)
        self.b = self.client('ai-b', poll_only=True)
        pending = self.b.pending_tool('read_messages', wait_seconds=10)
        self.b.call('ping')
        started = time.monotonic()
        self.a.tool('send_message', message='Fallback delivery')
        self.assertIn('result', self.b.receive(pending))
        self.assertLess(time.monotonic() - started, 3)
        self.b.pending_tool('read_messages', after_id=999, wait_seconds=30)
        self.b.call('ping')
        self.b.close()  # EOF cancels the outstanding 30-second wait.
        self.clients.remove(self.b)


class MigrationTests(unittest.TestCase):
    def test_old_database(self):
        with tempfile.TemporaryDirectory() as directory:
            dbpath = Path(directory) / 'old.sqlite3'
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,sender TEXT,recipient TEXT,body TEXT,created_at TEXT)')
                db.execute("INSERT INTO messages VALUES (1,'ai-a','ai-b','original','2026-01-01')")
                db.commit()
            store = Store(dbpath, 'ai-b', 'ai-a')
            self.assertEqual(store.read(0, 50)['messages'][0]['body'], 'original')
            self.assertEqual(store.read(0, 50)['messages'][0]['thread_id'], '')
            store.acknowledge(1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
