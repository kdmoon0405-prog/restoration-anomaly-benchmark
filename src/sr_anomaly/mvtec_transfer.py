"""Prepare unchanged category inputs and deterministic normal splits, without decoding images."""
from __future__ import annotations

import shutil
from pathlib import Path
import zipfile

from .analysis_io import csv_rows, digest, new_output, read_json, relative_source, write_csv, write_json
from .dataset import MVTecADFolder, safe_component
from .fusion import split_train_calibration

SOURCE_URL = "https://www.mvtec.com/research-teaching/datasets/mvtec-ad"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"


def prepare_transfer(data_root, output, *, categories=("hazelnut", "screw", "capsule"),
                     seeds=(11, 23, 37), train_ratio=0.8, pack=False):
    root = Path(data_root).resolve()
    categories, seeds = tuple(categories), tuple(seeds)
    if (not categories or len(set(categories)) != len(categories) or not seeds
            or len(set(seeds)) != len(seeds)
            or any(not isinstance(s, int) or isinstance(s, bool) or s < 0 for s in seeds)):
        raise ValueError("Categories/seeds must be nonempty and unique")
    for notice in ("license.txt", "readme.txt"):
        if not (root / notice).is_file():
            raise FileNotFoundError(f"Preserve the original dataset notice: {notice}")
    if "Attribution-NonCommercial-ShareAlike" not in (root / "license.txt").read_text(encoding="utf-8"):
        raise ValueError("Unexpected dataset license; review the actual source before sharing")
    summaries, file_rows, splits = [], [], []
    for category in categories:
        safe_component(category, "category")
        train = MVTecADFolder(root, category, "train").samples()
        test = MVTecADFolder(root, category, "test").samples()
        if any(s.metadata["label"] != 0 for s in train):
            raise ValueError("Official normal train split contains anomalies")
        if {s.relative_path for s in train} & {s.relative_path for s in test}:
            raise ValueError("Official train/test paths overlap")
        paths = sorted(p for p in (root / category).rglob("*") if p.is_file())
        for p in paths:
            relative = p.relative_to(root).as_posix()
            relative_source(root, relative)
            file_rows.append(dict(path=relative, category=category, bytes=p.stat().st_size, sha256=digest(p)))
        for seed in seeds:
            fit, calibration = split_train_calibration(len(train), train_ratio, seed)
            split = dict(category=category, seed=seed, train_ratio=train_ratio, train_count_total=len(train),
                train_count=len(fit), calibration_count=len(calibration), test_count=len(test),
                train_indices=fit, calibration_indices=calibration,
                train_paths=[train[i].relative_path.as_posix() for i in fit],
                calibration_paths=[train[i].relative_path.as_posix() for i in calibration],
                test_paths=[s.relative_path.as_posix() for s in test],
                test_labels=[s.metadata["label"] for s in test])
            splits.append(split)
        summaries.append(dict(category=category, train_normal=len(train),
            test_normal=sum(s.metadata["label"] == 0 for s in test),
            test_anomaly=sum(s.metadata["label"] == 1 for s in test),
            test_count=len(test), anomaly_mask_files=sum(s.mask_path is not None for s in test),
            files=len(paths), bytes=sum(p.stat().st_size for p in paths)))
    for name in ("license.txt", "readme.txt"):
        p = root / name
        file_rows.append(dict(path=name, category="dataset_notice", bytes=p.stat().st_size, sha256=digest(p)))
    expected_bytes = sum(r["bytes"] for r in file_rows)
    out = new_output(Path(output), [root])
    # Store paths and file digests only. No image/mask decoding or metric calculation.
    write_csv(out / "file_manifest.csv", file_rows)
    (out / "splits").mkdir()
    split_hashes = {}
    for split in splits:
        name = f"splits/{split['category']}-seed{split['seed']}.json"
        write_json(out / name, split)
        split_hashes[name] = digest(out / name)
    for notice in ("license.txt", "readme.txt"):
        shutil.copyfile(root / notice, out / notice)
    report = dict(kind="mvtec_category_transfer_inventory", schema_version=1,
        source_url=SOURCE_URL, license="CC BY-NC-SA 4.0", license_url=LICENSE_URL,
        modification="Category subset only; original file bytes unchanged",
        dataset_attribution="Copyright 2019 MVTec Software GmbH; see original readme.txt",
        image_decode_performed=False, geometry_or_mask_transform_performed=False,
        fit_calibration_split="Existing fusion.split_train_calibration on lexically sorted official train paths",
        train_ratio=train_ratio, seeds=list(seeds), categories=summaries,
        inventory_file="file_manifest.csv", inventory_sha256=digest(out / "file_manifest.csv"),
        splits_sha256=split_hashes, total_source_bytes=expected_bytes, archives=[])
    write_json(out / "input_manifest.json", report)
    if pack:
        # ZIP_STORED avoids spending CPU recompressing PNG files. Use one category per archive.
        if shutil.disk_usage(out).free < expected_bytes + 256 * 1024**2:
            raise OSError("Insufficient disk for category archives and 256MiB runtime margin")
        for category in categories:
            archive = out / (category + "-inputs.zip")
            with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
                for row in file_rows:
                    if row["category"] in (category, "dataset_notice"):
                        z.write(relative_source(root, row["path"]), "MVTecAD/" + row["path"])
                for name in ("input_manifest.json", "file_manifest.csv", "license.txt", "readme.txt", *split_hashes):
                    z.write(out / name, "transfer_metadata/" + name)
            report["archives"].append(dict(file=archive.name, bytes=archive.stat().st_size, sha256=digest(archive)))
        # Archive copies contain the initial inventory, avoiding self-referential archive hashes.
        write_json(out / "input_manifest.json", report)
    (out / "TRANSFER.md").write_text(
        "# MVTec AD category input transfer\n\n"
        "Use for noncommercial research with attribution and the original CC BY-NC-SA 4.0 notices.\n"
        f"Official dataset: {SOURCE_URL}\nLicense: {LICENSE_URL}\n\n"
        "Extract each received category archive into a common folder containing MVTecAD/.\n"
        "Original RGB/GT bytes are unchanged; category selection is the only packaging change.\n"
        "The global inventory can be verified with --category for only the categories received.\n"
        "Splits use the existing train/calibration function. No test image enters either normal split.\n"
        "Hash verification does not establish decoded RGB/mask geometry or model correctness.\n"
        "Keep data archives and inventories local; do not commit them to Git.\n", encoding="utf-8")
    return report


def verify_transfer(manifest_path, data_root, *, categories=None):
    manifest_path = Path(manifest_path).resolve()
    report = read_json(manifest_path)
    if report.get("kind") != "mvtec_category_transfer_inventory" or report.get("schema_version") != 1:
        raise ValueError("Unsupported input manifest")
    inventory = relative_source(manifest_path.parent, report["inventory_file"])
    if digest(inventory) != report["inventory_sha256"]:
        raise ValueError("Inventory digest mismatch")
    chosen = set(categories or [x["category"] for x in report["categories"]])
    known = {x["category"] for x in report["categories"]}
    if not chosen or not chosen <= known:
        raise ValueError("Requested categories are absent from the manifest")
    count = total = 0
    for row in csv_rows(inventory, ("path", "category", "bytes", "sha256")):
        if row["category"] not in chosen | {"dataset_notice"}:
            continue
        p = relative_source(Path(data_root), row["path"])
        if not p.is_file() or p.stat().st_size != int(row["bytes"]) or digest(p) != row["sha256"]:
            raise ValueError("Missing or modified input: " + row["path"])
        count += 1
        total += p.stat().st_size
    for name, expected in report["splits_sha256"].items():
        if digest(relative_source(manifest_path.parent, name)) != expected:
            raise ValueError("Split manifest changed")
    return dict(status="FILE_HASHES_VERIFIED", categories=sorted(chosen), files=count, bytes=total,
                decoded_inputs_verified=False, model_execution=False)
