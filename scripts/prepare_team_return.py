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


def prepare(source, repo_root, owner, run_id, includes):
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
        body.decode('utf-8-sig')
        if b'\x00' in body:
            raise ValueError('Binary content in text artifact')
        files.append((relative.as_posix(), body))
    # Explicit selection and text checks do not replace the sender's disclosure review.
    receipt = {
        'schema': 'team-public-text-return-v1', 'owner': owner, 'run_id': run_id,
        'prepared_utc': datetime.now(timezone.utc).isoformat(),
        'review_status': 'NOT_REVIEWED', 'array_contents_verified': False,
        'files': [dict(path=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
                  for name, body in files],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.prepare-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'return'
        staged.mkdir()
        for name, body in files:
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
    args = parser.parse_args()
    try:
        print(prepare(args.source, args.repo_root, args.owner, args.run_id, args.include))
        return 0
    except (ValueError, OSError) as error:
        print(str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
