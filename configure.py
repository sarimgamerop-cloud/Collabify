"""Make connection instructions for any two local MCP-compatible AI apps."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys

APPS = {'codex': 'Codex', 'antigravity': 'Antigravity', 'claude-code': 'Claude Code',
        'claude-desktop': 'Claude Desktop', 'other': 'Another MCP app'}


def choose(label):
    print(f'\n{label}')
    keys = list(APPS)
    for number, key in enumerate(keys, 1):
        print(f'  {number}. {APPS[key]}')
    while True:
        value = input('Choose a number: ').strip()
        if value.isdigit() and 1 <= int(value) <= len(keys):
            return keys[int(value) - 1]
        print('Please enter a number from 1 to 5.')


def shell_command(parts):
    if os.name == 'nt':
        # Literal PowerShell arguments, including paths with spaces and apostrophes.
        return parts[0] + ' ' + ' '.join("'" + value.replace("'", "''") + "'" for value in parts[1:])
    return shlex.join(parts)


def generate(root, output, database, first='codex', second='antigravity'):
    output.mkdir(parents=True, exist_ok=True)
    command = str(Path(sys.executable).resolve())
    instructions = ['AI Messenger: your connection instructions', '',
                    'Open docs/CLIENTS.md for help finding your app settings.',
                    f'Both apps will share this message file: {database}',
                    'These files do not change your apps automatically.', '']
    if first == second:
        instructions += ['You chose the same app twice. Use separate profiles or separate workspace',
                         'settings for A and B. Saving both identities in one global server entry',
                         'would replace one with the other. See docs/CLIENTS.md.', '']
    for identity, app in [('ai-a', first), ('ai-b', second)]:
        args = [str(root / 'server.py'), '--db', str(database), '--identity', identity]
        config = {'mcpServers': {'ai-messenger': {'command': command, 'args': args}}}
        json_name = f'{identity}.json'
        toml_name = f'{identity}.codex.toml'
        payload = json.dumps(config, indent=2) + '\n'
        toml = '[mcp_servers.ai-messenger]\ncommand = ' + json.dumps(command) + '\nargs = ' + json.dumps(args) + '\n'
        (output / json_name).write_text(payload, encoding='utf-8')
        (output / toml_name).write_text(toml, encoding='utf-8')
        instructions += [f'{identity.upper()} = {APPS[app]}']
        if app == 'codex':
            executable = 'codex.cmd' if os.name == 'nt' else 'codex'
            instructions += ['Run this in your own terminal:',
                             shell_command([executable, 'mcp', 'add', 'ai-messenger', '--', command, *args]),
                             f'Or merge {toml_name} into your Codex config.toml.']
        elif app == 'claude-code':
            instructions += ['Run this in your own terminal:',
                             shell_command(['claude', 'mcp', 'add', '--transport', 'stdio', '--scope', 'user',
                                            'ai-messenger', '--', command, *args]),
                             'For separate workspaces of the same app, use --scope local instead of user.']
        elif app == 'antigravity':
            instructions += [f'Merge the server entry from {json_name} into ~/.gemini/config/mcp_config.json.']
        elif app == 'claude-desktop':
            instructions += [f'Merge the server entry from {json_name} into claude_desktop_config.json.',
                             'Find the file through Claude Desktop settings; see docs/CLIENTS.md.']
        else:
            instructions += [f'Use {json_name} if your app accepts an mcpServers JSON file.',
                             'If it asks for fields instead, choose local / stdio and use:',
                             f'Command: {command}', 'Arguments (one item per line):', *args]
        instructions += ['Keep any other servers already in your settings.',
                         'Restart the app, enable ai-messenger, and ask it to use whoami.',
                         f'It should report identity {identity}.', '']
    instructions += ['Once both apps are connected, use the starter messages in README.md.',
                     'You do not need to start server.py yourself. The apps do that for you.']
    (output / 'START-HERE.txt').write_text('\n'.join(instructions) + '\n', encoding='utf-8')
    # Keep the original generator's default filenames working for existing users.
    if (first, second) == ('codex', 'antigravity'):
        (output / 'codex.toml').write_text((output / 'ai-a.codex.toml').read_text(encoding='utf-8'), encoding='utf-8')
        (output / 'antigravity.json').write_text((output / 'ai-b.json').read_text(encoding='utf-8'), encoding='utf-8')
    return output / 'START-HERE.txt'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', choices=APPS, default='codex', help='App for AI A')
    parser.add_argument('--second', choices=APPS, default='antigravity', help='App for AI B')
    parser.add_argument('--interactive', action='store_true', help='Choose your apps from a simple menu')
    parser.add_argument('--db', type=Path, help='Use an existing shared message file')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'generated')
    args = parser.parse_args()
    if args.interactive:
        args.first = choose('Which app will be AI A?')
        args.second = choose('Which app will be AI B?')
    root = Path(__file__).resolve().parent
    database = (args.db or root / 'messages.sqlite3').resolve()
    guide = generate(root, args.output, database, args.first, args.second)
    print(f'\nReady! Open this file for your next steps:\n{guide.resolve()}')
    print('Your app settings have not been changed.')


if __name__ == '__main__':
    main()
