"""Copy explicitly selected public result text into a new, checksummed return folder."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from tempfile import TemporaryDirectory


TEXT_SUFFIXES = {'.csv', '.json', '.md', '.txt'}
MAX_FILE_BYTES = 10 * 1024**2
MAX_TOTAL_BYTES = 50 * 1024**2
PRIVATE_PARTS = {'.git', '.venv', 'notes', 'credentials', 'checkpoints'}
# Absolute local paths anywhere in text: drive letters (plain or JSON-escaped) or common POSIX user prefixes.
# JSON string values are additionally checked structurally (incl. UNC) by _is_absolute_path.
ABSOLUTE_PATH_PATTERN = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:(?:\\|/)|(?<![\w.])/(?:Users|home|mnt|root)/')


def _is_absolute_path(value):
    windows = PureWindowsPath(value)
    return bool((windows.drive and windows.root) or value.startswith('\\\\')
                or (value.startswith('/') and len(PurePosixPath(value).parts) > 1))


def _relative_to_root(value, local_roots):
    flavour = PureWindowsPath if PureWindowsPath(value).drive or value.startswith('\\\\') else PurePosixPath
    for root in local_roots:
        try:
            relative = flavour(value).relative_to(flavour(root))
        except ValueError:
            continue
        return PurePosixPath(*relative.parts).as_posix() if relative.parts else '.'
    return None


def _refuse_absolute_text(text, name):
    if ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError(f'Absolute local path in {name}; write repository-relative paths or pass --local-root for JSON')


def _public_json(body, name, local_roots):
    """Return (public bytes, changes). Only string values that are absolute paths under a local root change.

    The rewrite is textual on the encoded literal so all other bytes stay identical; the parsed result
    must equal the original object with exactly those values replaced.
    """
    text = body.decode('utf-8-sig')
    changes = []

    def walk(value, pointer):
        if isinstance(value, dict):
            return {k: walk(v, f"{pointer}/{k.replace('~', '~0').replace('/', '~1')}") for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, f'{pointer}/{i}') for i, v in enumerate(value)]
        if isinstance(value, str) and _is_absolute_path(value):
            relative = _relative_to_root(value, local_roots)
            if relative is None:
                raise ValueError(f'Absolute local path outside --local-root in {name} at {pointer or "/"}')
            changes.append((pointer, value, relative))
            return relative
        return value

    public = walk(json.loads(text), '')
    new = text
    for _, old, relative in changes:
        literals = [c for c in dict.fromkeys((json.dumps(old), json.dumps(old, ensure_ascii=False))) if c in new]
        if not literals:
            raise ValueError(f'Cannot rewrite path literal byte-preservingly in {name}')
        for literal in literals:
            new = new.replace(literal, json.dumps(relative))
    if json.loads(new) != public:
        raise ValueError(f'Path rewrite would change other JSON values in {name}')
    _refuse_absolute_text(new, name)
    if not changes:
        return body, []
    bom = b'\xef\xbb\xbf' if body.startswith(b'\xef\xbb\xbf') else b''
    return bom + new.encode('utf-8'), [dict(field=p, public_value=r) for p, _, r in changes]


def prepare(source, repo_root, owner, run_id, includes, local_roots=()):
    local_roots = [str(Path(r).resolve()) for r in local_roots]
    if owner not in {'juhyung', 'jihyuk'}:
        raise ValueError('Unknown owner')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', run_id):
        raise ValueError('Use a unique alphanumeric run ID with optional hyphens/underscores')
    source, repo_root = Path(source).resolve(), Path(repo_root).resolve()
    destination = repo_root / 'handoff' / 'returns' / owner / run_id
    if destination.exists():
        raise FileExistsError('Existing returns are preserved; choose a new run ID')
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and return output must be separate directories')
    if not includes:
        raise ValueError('Select at least one public text artifact explicitly')
    seen, files, total = set(), [], 0
    for name in includes:
        relative = PurePosixPath(name)
        if (not relative.parts or relative.is_absolute() or PureWindowsPath(name).drive
                or '\\' in name or ':' in name
                or any(p in {'.', '..'} or p.startswith('.') or p.rstrip(' .') != p
                       for p in relative.parts)):
            raise ValueError('Unsafe relative artifact path')
        if (relative.suffix.lower() not in TEXT_SUFFIXES
                or PRIVATE_PARTS.intersection(p.casefold() for p in relative.parts)
                or relative.name.casefold() == 'receipt.json'):
            raise ValueError('Only public CSV/JSON/Markdown/text artifacts are accepted')
        key = relative.as_posix().casefold()
        if key in seen:
            raise ValueError('Duplicate artifact path')
        seen.add(key)
        path = source.joinpath(*relative.parts)
        if (not path.is_file() or not path.resolve().is_relative_to(source)
                or any(p.is_symlink() for p in [path, *path.parents] if p != source)):
            raise ValueError('Missing artifact or symbolic link')
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Text return exceeds the 10 MiB/file or 50 MiB/return limit')
        body = path.read_bytes()
        if b'\x00' in body:
            raise ValueError('Binary content in text artifact')
        original = body
        if relative.suffix.lower() == '.json':
            body, changes = _public_json(body, relative.as_posix(), local_roots)
        else:
            _refuse_absolute_text(body.decode('utf-8-sig'), relative.as_posix())
            changes = []
        files.append((relative.as_posix(), body, original, changes))
    # Explicit selection and text checks do not replace the sender's disclosure review.
    receipt = {
        'schema': 'team-public-text-return-v1', 'owner': owner, 'run_id': run_id,
        'prepared_utc': datetime.now(timezone.utc).isoformat(),
        'review_status': 'NOT_REVIEWED', 'array_contents_verified': False,
        'files': [dict(path=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                       **({'public_path_view': True, 'original_bytes': len(original),
                           'original_sha256': hashlib.sha256(original).hexdigest(), 'changed_fields': changes}
                          if changes else {}))
                  for name, body, original, changes in files],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.prepare-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'return'
        staged.mkdir()
        for name, body, _, _ in files:
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        (staged / 'RECEIPT.json').write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        if destination.exists():
            raise FileExistsError('Return appeared concurrently; choose a new run ID')
        staged.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--owner', choices=['juhyung', 'jihyuk'], required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--include', nargs='+', required=True)
    parser.add_argument('--local-root', action='append', default=[],
                        help='Local directory whose absolute paths in JSON values are rewritten repository-relative; '
                             'the receipt keeps the original SHA-256 and changed fields. Other absolute paths are refused.')
    args = parser.parse_args()
    try:
        print(prepare(args.source, args.repo_root, args.owner, args.run_id, args.include, args.local_root))
        return 0
    except (ValueError, OSError) as error:
        print(str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
