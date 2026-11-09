"""Verify and receive a private category transfer into a new data directory."""
from pathlib import Path, PurePosixPath
import argparse
import csv
import hashlib
import io
import json
import shutil
import stat
import zipfile


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(name):
    value = PurePosixPath(name)
    if (not name or '\\' in name or value.is_absolute()
            or any(part == '..' or ':' in part or part.rstrip(' .') != part for part in value.parts)):
        raise ValueError('Unsafe transfer path')
    return value.as_posix()


def receive(archive, receipt_path, output):
    archive, receipt_path, output = map(Path, (archive, receipt_path, output))
    receipt = json.loads(receipt_path.read_text('utf-8-sig'))
    if (receipt['dataset'] != 'MVTec AD' or receipt['categories'] != ['hazelnut', 'screw']
            or receipt['archive_sha256_role'] != 'private_team_category_repack'
            or sha(archive) != receipt['archive_sha256']):
        raise ValueError('Transfer receipt/archive mismatch')
    if output.exists():
        raise FileExistsError('Choose a new data directory; existing inputs are preserved')
    with zipfile.ZipFile(archive) as z:
        entries = {}
        seen = set()
        for entry in z.infolist():
            name = safe_name(entry.filename)
            if name.casefold() in seen or entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Duplicate path, directory entry or symlink')
            seen.add(name.casefold())
            entries[name] = entry
        manifest_bytes = z.read('FILE_MANIFEST.csv')
        if hashlib.sha256(manifest_bytes).hexdigest() != receipt['input_inventory_sha256']:
            raise ValueError('Input manifest hash mismatch')
        rows = list(csv.DictReader(io.StringIO(manifest_bytes.decode('utf-8-sig'))))
        names = [safe_name(row['path']) for row in rows]
        if (len(set(names)) != len(names) or set(names) | {'FILE_MANIFEST.csv'} != set(entries)
                or 'dataset_provenance.json' in names):
            raise ValueError('Input manifest file set mismatch')
        total = sum(entry.file_size for entry in entries.values())
        ancestor = output.parent.resolve()
        while not ancestor.exists():
            ancestor = ancestor.parent
        if total > 2 * 1024**3 or shutil.disk_usage(ancestor).free < total + 2 * 1024**3:
            raise OSError('Insufficient disk or transfer exceeds 2 GiB uncompressed limit')
        output.mkdir(parents=True)
        for row, name in zip(rows, names, strict=True):
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            count = 0
            with z.open(name) as source, path.open('xb') as target:
                while block := source.read(1024**2):
                    h.update(block)
                    count += len(block)
                    target.write(block)
            if h.hexdigest() != row['sha256'] or count != int(row['bytes']):
                raise ValueError('Transferred file mismatch: ' + name)
        if sha(output / safe_name(receipt['license_file'])) != receipt['license_sha256']:
            raise ValueError('License hash mismatch')
        (output / 'FILE_MANIFEST.csv').write_bytes(manifest_bytes)
        # The runner receives its receipt only after every file has passed.
        (output / 'dataset_provenance.json').write_bytes(receipt_path.read_bytes())
    return dict(status='TRANSFER_VERIFIED',files=len(rows),archive_role=receipt['archive_sha256_role'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(receive(args.archive, args.receipt, args.output)))
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print(str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
