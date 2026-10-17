"""Install the frozen pcb2 inputs, never run models or change research settings."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "analysis/pcb_geometry/pcb2-native224-tiling-20261016"
CONFIG = ROOT / "configs/pcb_gpu_inputs.json"
LEGAL = {"LICENSE-DATASET", "NOTICE", "ATTRIBUTION.md"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def target_path(root, name):
    relative = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or relative.is_absolute()
            or relative.as_posix() != name or ".." in relative.parts):
        raise ValueError(f"Unsafe input path: {name}")
    root = Path(root).resolve()
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(f"Symlink input target refused: {name}")
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"Unsafe input path: {name}")
    return target


def expected_files():
    protocol = json.loads((AUDIT / "PROTOCOL.json").read_text(encoding="utf-8"))
    expected = {"split_csv/1cls.csv": protocol["official_csv_sha256"]}
    with (AUDIT / "INPUTS.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1101:
        raise ValueError("Frozen 1101-board pcb2 inventory required")
    for row in rows:
        expected[row["sample"]] = row["image_sha256"]
        if row["mask"]:
            expected[row["mask"]] = row["mask_sha256"]
    return expected


def verify_existing(root, expected, *, require_all=False):
    missing = []
    for name, digest in expected.items():
        path = target_path(root, name)
        if not path.exists():
            missing.append(name)
        elif not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Existing file differs; refusing overwrite: {path}")
    if require_all and missing:
        raise ValueError(f"Missing {len(missing)} input files; first: {missing[0]}")
    return missing


def download(url, destination, expected_sha):
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("Symlink download target refused")
    if destination.exists():
        if sha256(destination) != expected_sha:
            raise ValueError(f"Existing download differs; refusing overwrite: {destination}")
        return destination
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS input downloads are allowed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {destination.name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="pcb-download-", dir=destination.parent) as temp:
        staged = Path(temp) / "payload"
        request = urllib.request.Request(url, headers={"User-Agent": "pcb-frozen-input-setup"})
        with urllib.request.urlopen(request, timeout=120) as response, staged.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if sha256(staged) != expected_sha:
            raise ValueError(f"Downloaded SHA256 mismatch: {destination.name}")
        # Same-filesystem hard link provides no-overwrite publication on Windows/Linux.
        os.link(staged, destination)
    return destination


def install_bundle(archive, visa_root, expected, bundle_sha):
    if sha256(archive) != bundle_sha:
        raise ValueError("Bundle SHA256 mismatch")
    verify_existing(visa_root, expected)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [entry.filename for entry in members]
        if len(names) != len(set(names)) or set(names) != set(expected) | LEGAL:
            raise ValueError("Bundle entries differ from frozen allowlist")
        for entry in members:
            target_path(visa_root, entry.filename)
            if entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Directory/symlink bundle member refused")
            if entry.filename in expected:
                with bundle.open(entry) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected[entry.filename]:
                        raise ValueError(f"Bundle member hash mismatch: {entry.filename}")
        # Validate all members before creating dataset files. Resume accepts identical files only.
        for entry in members:
            target = target_path(visa_root, entry.filename)
            if target.exists():
                with bundle.open(entry) as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if not target.is_file() or sha256(target) != digest:
                    raise ValueError(f"Existing file differs: {target}")
        for entry in members:
            target = target_path(visa_root, entry.filename)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="pcb-install-", dir=target.parent) as temp:
                staged = Path(temp) / "payload"
                with bundle.open(entry) as source, staged.open("xb") as output:
                    shutil.copyfileobj(source, output)
                os.link(staged, target)
    verify_existing(visa_root, expected, require_all=True)


def build_bundle(visa_root, output, expected):
    """Release producer: exact frozen subset with license and attribution, no transformed RGB."""
    verify_existing(visa_root, expected, require_all=True)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    legal_sources = {"LICENSE-DATASET": Path(visa_root) / "LICENSE-DATASET",
                     "NOTICE": ROOT / "docs/third_party/VISA_NOTICE.txt",
                     "ATTRIBUTION.md": ROOT / "docs/third_party/VISA_ATTRIBUTION.md"}
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as bundle:
        for name in sorted(set(expected) | LEGAL):
            source = legal_sources[name] if name in LEGAL else target_path(visa_root, name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            with Path(source).open("rb") as stream, bundle.open(info, "w") as dest:
                shutil.copyfileobj(stream, dest)
    result = {"name": output.name, "bytes": output.stat().st_size,
              "sha256": sha256(output), "entries": len(expected) + len(LEGAL)}
    print(json.dumps(result, indent=2))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visa-root", type=Path, default=ROOT / "data/external/VisA")
    parser.add_argument("--cache", type=Path, default=ROOT / "outputs/pcb-input-downloads")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--build-bundle", type=Path, help="producer only: create a NEW licensed pcb2 ZIP")
    args = parser.parse_args(argv)
    expected = expected_files()
    if args.build_bundle:
        build_bundle(args.visa_root, args.build_bundle, expected)
        return 0
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    torch_home = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache/torch"))
    checkpoints = [(config["backbone"], Path(os.environ.get("PATCHCORE_BACKBONE_CHECKPOINT",
                    torch_home / "hub/checkpoints" / config["backbone"]["name"]))),
                   (config["swinir"], Path(os.environ.get("SWINIR_X4_CHECKPOINT",
                    ROOT / "checkpoints/swinir" / config["swinir"]["name"])))]
    verify_existing(args.visa_root, expected)
    if args.verify_only:
        verify_existing(args.visa_root, expected, require_all=True)
        for item, path in checkpoints:
            if not path.is_file() or sha256(path) != item["sha256"]:
                raise ValueError(f"Checkpoint missing/hash mismatch: {path}")
    else:
        if verify_existing(args.visa_root, expected):
            item = config["bundle"]
            archive = download(item["url"], args.cache / item["name"], item["sha256"])
            install_bundle(archive, args.visa_root, expected, item["sha256"])
        for item, path in checkpoints:
            download(item["url"], path, item["sha256"])
    print(json.dumps({"status": "PCB_INPUTS_VERIFIED", "files": len(expected),
                      "visa_root": str(args.visa_root.resolve()),
                      "backbone_checkpoint": str(checkpoints[0][1].resolve()),
                      "swinir_checkpoint": str(checkpoints[1][1].resolve()),
                      "models_executed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
