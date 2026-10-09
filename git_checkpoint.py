"""Persist state to GitHub before a visible side effect on disposable runners."""
import os
from pathlib import Path
import subprocess


class CheckpointError(RuntimeError):
    pass


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    if result.returncode:
        # Git output can contain authenticated remotes. Keep it out of public logs.
        raise CheckpointError('Durable Git checkpoint failed; no automatic publish retry')
    return result.stdout.strip()


def checkpoint(root, run):
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GAJEONSO_DURABLE_GIT') != '1':
        raise CheckpointError('GitHub Actions requires durable Git checkpoints')
    if os.environ.get('GAJEONSO_DURABLE_GIT') != '1':
        return
    root = Path(root)
    if git(root, 'branch', '--show-current') != 'main':
        raise CheckpointError('Durable publishing requires main')
    git(root, 'fetch', '--quiet', 'origin', 'main')
    if git(root, 'rev-parse', 'HEAD') != git(root, 'rev-parse', 'FETCH_HEAD'):
        raise CheckpointError('Remote main changed; restart with latest state')
    paths = ['log']
    if (root / 'cards' / run).exists():
        paths.append('cards/' + run)
    git(root, 'add', '--', *paths)
    staged = git(root, 'diff', '--cached', '--name-only')
    if not staged:
        return
    if any(not (path.startswith('log/') or path.startswith('cards/' + run + '/'))
           for path in staged.splitlines()):
        raise CheckpointError('Unrelated staged changes; checkpoint refused')
    git(root, '-c', 'user.name=github-actions[bot]', '-c',
        'user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit', '--quiet', '-m', 'automation: checkpoint ' + run + ' [skip ci]')
    # A concurrent stale writer cannot fast-forward over our durable marker.
    git(root, 'push', '--quiet', 'origin', 'HEAD:refs/heads/main')
