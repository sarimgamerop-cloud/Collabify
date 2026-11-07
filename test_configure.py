"""Verify client-neutral configs and real launches without modifying app settings."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from configure import APPS, choose, generate

ROOT = Path(__file__).resolve().parent


class ConfigurationTests(unittest.TestCase):
    def test_every_app_pair_has_opposite_mailboxes_and_shared_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            db = root / 'shared messages.sqlite3'
            for first in APPS:
                for second in APPS:
                    with self.subTest(first=first, second=second):
                        output = root / f'{first}-{second}'
                        guide = generate(ROOT, output, db, first, second)
                        instructions = guide.read_text(encoding='utf-8')
                        self.assertIn(f'AI-A = {APPS[first]}', instructions)
                        self.assertIn(f'AI-B = {APPS[second]}', instructions)
                        for identity in ('ai-a', 'ai-b'):
                            server = json.loads((output / f'{identity}.json').read_text())['mcpServers']['ai-messenger']
                            toml = tomllib.loads((output / f'{identity}.codex.toml').read_text())['mcp_servers']['ai-messenger']
                            self.assertEqual(server, toml)
                            self.assertEqual(server['args'][-1], identity)
                            self.assertEqual(server['args'][2], str(db))
                            self.assertTrue(Path(server['command']).is_absolute())
                        if first == second:
                            self.assertIn('separate profiles', instructions)

    def test_generated_commands_launch_from_a_path_with_spaces_and_apostrophe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "someone's project folder"
            root.mkdir()
            for filename in ('server.py', 'protocol.py', 'store.py'):
                shutil.copy2(ROOT / filename, root / filename)
            output = root / 'generated'
            generate(root, output, root / 'shared messages.sqlite3', 'claude-code', 'other')
            for identity in ('ai-a', 'ai-b'):
                server = json.loads((output / f'{identity}.json').read_text())['mcpServers']['ai-messenger']
                requests = [
                    {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'whoami'}},
                ]
                result = subprocess.run([server['command'], *server['args']],
                                        input=''.join(json.dumps(r) + '\n' for r in requests),
                                        text=True, encoding='utf-8', capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                replies = {r['id']: r for r in map(json.loads, result.stdout.splitlines())}
                self.assertIn('result', replies[1])
                payload = json.loads(replies[2]['result']['content'][0]['text'])
                self.assertEqual(payload['identity'], identity)

    def test_menu_rejects_invalid_input_and_keeps_legacy_default_files(self):
        with patch('builtins.input', side_effect=['wrong', '0', '3']), patch('builtins.print'):
            self.assertEqual(choose('First app'), 'claude-code')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate(ROOT, output, output / 'messages.sqlite3')
            self.assertEqual((output / 'codex.toml').read_text(), (output / 'ai-a.codex.toml').read_text())
            self.assertEqual((output / 'antigravity.json').read_text(), (output / 'ai-b.json').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
