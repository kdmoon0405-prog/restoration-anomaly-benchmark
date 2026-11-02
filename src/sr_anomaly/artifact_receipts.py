"""Cache metadata ZIP inventory/hash checks; never infer remote execution or array validity."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .analysis_io import digest, read_json, write_json

POLICY_VERSION = 1


def _name(value):
    path = PurePosixPath(value)
    if (not value or "\\" in value or path.is_absolute()
            or any(p in (".", "..") or ":" in p or p.rstrip(" .") != p for p in path.parts)):
        raise ValueError("Unsafe archive/manifest path")
    return path.as_posix()


def review_archive(archive, cache, *, max_uncompressed_bytes=128 * 1024**2):
    archive, cache = Path(archive).resolve(), Path(cache).resolve()
    sha = digest(archive)
    receipt_path = cache / f"v{POLICY_VERSION}-{sha}.json"
    if receipt_path.is_file():
        old = read_json(receipt_path)
        if (old.get("policy_version") == POLICY_VERSION and old.get("archive_sha256") == sha
                and old.get("status") == "METADATA_INVENTORY_CHECKED"):
            return dict(old, cache_hit=True)
    inventory, hashes = {}, {}
    with zipfile.ZipFile(archive) as z:
        seen = set()
        for info in z.infolist():
            name = _name(info.filename.rstrip("/"))
            if name.casefold() in seen or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Duplicate archive path or symlink")
            seen.add(name.casefold())
            if not info.is_dir():
                inventory[name] = dict(bytes=info.file_size,
                    content_role="array_not_decoded" if Path(name).suffix.lower() in (".npy", ".npz")
                    else "metadata_or_other")
        if sum(v["bytes"] for v in inventory.values()) > max_uncompressed_bytes:
            raise ValueError("Metadata ZIP exceeds the explicit uncompressed-size budget")
        manifests = [n for n in inventory if PurePosixPath(n).name in ("SHA256SUMS", "SHA256SUMS.txt")]
        checked = set()
        for manifest in manifests:
            for line in z.read(manifest).decode("utf-8-sig").splitlines():
                if not line.strip():
                    continue
                expected, relative = line.split(None, 1)
                relative = relative.strip().lstrip("*")
                relative = _name(relative)
                name = (PurePosixPath(manifest).parent / relative).as_posix()
                if name not in inventory or len(expected) != 64:
                    raise ValueError("Manifest references a missing file or malformed digest")
                if name not in hashes:
                    with z.open(name) as stream:
                        hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
                if hashes[name] != expected.lower():
                    raise ValueError("Archive manifest digest mismatch: " + name)
                checked.add(name)
    receipt = dict(policy_version=POLICY_VERSION, status="METADATA_INVENTORY_CHECKED",
        archive_sha256=sha, archive_bytes=archive.stat().st_size,
        manifests=len(manifests), manifest_entries_verified=len(checked),
        files=inventory, unlisted_files=sorted(set(inventory) - checked - set(manifests)),
        supplied_array_files=[n for n in inventory if inventory[n]["content_role"] == "array_not_decoded"],
        raw_array_content_checked=False, remote_execution_independently_observed=False,
        source_binding_independently_checked=False, research_acceptance_inferred=False,
        scope="Inventory and supplied manifest hashes only; source/model/metric review is separate")
    cache.mkdir(parents=True, exist_ok=True)
    write_json(receipt_path, receipt)
    return dict(receipt, cache_hit=False)
