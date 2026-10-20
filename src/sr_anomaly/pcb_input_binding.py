"""Hash-bound native RGB/GT callbacks; no model, resize or performance metrics."""
from __future__ import annotations

import csv
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
from PIL import Image

from .bounded_bank import file_sha256
from .dataset import safe_component
from .pcb_board_analysis import RAM_RESERVE, _budget
from .pcb_native_memory import evaluation_mask, write_json
from .pcb_tiled_runner import GEOMETRY, available_ram, load_inventory, safe_source
from .tiled_cpu_pipeline import Parent

KIND = "frozen_input_binding_cpu_audit_not_model_results"
PARTITIONS = {"fit": {"normal": 721, "anomaly": 0},
              "calibration": {"normal": 180, "anomaly": 0},
              "test": {"normal": 100, "anomaly": 100}}
CODE = ("src/sr_anomaly/pcb_input_binding.py", "scripts/check_pcb_input_binding.py",
        "src/sr_anomaly/pcb_native_memory.py", "src/sr_anomaly/pcb_tiled_runner.py",
        "src/sr_anomaly/pcb_board_analysis.py", "src/sr_anomaly/evaluation.py")


class FrozenPCBInputs:
    """Construct from the frozen geometry; construction reads no RGB/GT content."""

    def __init__(self, root, data_root):
        self.root, self.data_root = Path(root).resolve(), Path(data_root).resolve()
        directory = self.root / GEOMETRY
        self.parents, rows, manifest = load_inventory(directory)
        if manifest["partitions"] != PARTITIONS:
            raise ValueError("Frozen pcb2 721/180/200 split required")
        self._parents = {p.sample: p for p in self.parents}
        self._rows = {r["sample"]: dict(r) for r in rows}
        protocol = json.loads((directory / "PROTOCOL.json").read_text(encoding="utf-8"))
        self.references = {str((GEOMETRY / name).as_posix()): file_sha256(directory / name)
                           for name in ("MANIFEST.json", "PROTOCOL.json", "INPUTS.csv", "layouts.json")}
        self.official_sha256 = protocol["official_csv_sha256"]
        self.geometry_id = manifest["geometry_id"]
        for parent in self.parents:
            row = self._rows[parent.sample]
            safe_source(self.data_root, parent.sample)
            if bool(row["mask"]) != bool(parent.label) or bool(row["mask_sha256"]) != bool(parent.label):
                raise ValueError("Only anomalous test parents may have frozen mask files")
            for key in ("image_sha256", "mask_sha256"):
                digest = row[key]
                if digest and (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
                    raise ValueError("Invalid frozen source checksum")
            if row["mask"]:
                safe_source(self.data_root, row["mask"])
        self.rgb_receipts, self.gt_receipts = {}, {}
        self.verify_references()

    def verify_references(self):
        for name, expected in self.references.items():
            if file_sha256(self.root / name) != expected:
                raise ValueError("Frozen input binding metadata changed")
        official = safe_source(self.data_root, "split_csv/1cls.csv")
        if file_sha256(official) != self.official_sha256:
            raise ValueError("Official VisA split CSV hash mismatch")

    def _row(self, parent):
        if not isinstance(parent, Parent) or self._parents.get(parent.sample) != parent:
            raise ValueError("Parent differs from frozen path/split/label/native geometry")
        return self._rows[parent.sample]

    def rgb(self, parent):
        row = self._row(parent)
        raw = safe_source(self.data_root, parent.sample).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != row["image_sha256"]:
            raise ValueError("Source RGB hash mismatch")
        # Decode the SAME verified bytes, not a second open vulnerable to a changed file.
        with Image.open(io.BytesIO(raw)) as image:
            mode = image.mode
            values = np.asarray(image.convert("RGB"))
        if values.dtype != np.uint8 or values.shape != (*parent.size_wh[::-1], 3):
            raise ValueError("Native RGB shape/dtype mismatch; no resizing/padding allowed")
        self.rgb_receipts[parent.sample] = dict(asdict(parent), file_sha256=digest,
            source_mode=mode, decoded_rgb_sha256=hashlib.sha256(values).hexdigest(),
            dtype="uint8", shape=list(values.shape), coordinate_transform="identity_no_exif_transpose")
        return values

    def evaluation_mask(self, parent):
        row = self._row(parent)
        mask = evaluation_mask(parent, self._rows, self.data_root)
        self.gt_receipts[parent.sample] = dict(asdict(parent), mask_path=row["mask"] or None,
            file_sha256=row["mask_sha256"] or None,
            source="frozen_file" if parent.label else "implicit_zero_no_file",
            binary_sha256=hashlib.sha256(mask).hexdigest(), dtype="bool", shape=list(mask.shape))
        return mask


def _csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _hash_receipt(inputs, parent, *, gt=False):
    row = inputs._row(parent)
    if gt and parent.split != "test":
        raise ValueError("GT file audit is test-only")
    name = row["mask"] if gt else parent.sample
    expected = row["mask_sha256"] if gt else row["image_sha256"]
    digest = file_sha256(safe_source(inputs.data_root, name)) if name else None
    if digest != (expected or None):
        raise ValueError("Frozen source file hash mismatch")
    return dict(asdict(parent), source_path=name or None, file_sha256=digest,
                source="frozen_file" if name else "implicit_zero_policy_no_file",
                decode_validated=False)


def audit(root, run_id, data_root, *, execute=False, hashes_only=False, output_base=None):
    """One native RGB or mask at a time; GT is consumed only in its named phase."""
    root = Path(root).resolve()
    if hashes_only and not execute:
        raise ValueError("Hash-only file audit also requires explicit execute")
    output = Path(output_base or root / "outputs/pcb-input-binding") / safe_component(run_id, "run ID")
    for source in (Path(data_root).resolve(), root / GEOMETRY):
        if output.resolve().is_relative_to(source) or source.is_relative_to(output.resolve()):
            raise ValueError("Audit output and source trees must be disjoint")
    output.mkdir(parents=True, exist_ok=False)
    state = {"kind": KIND, "status": "BUILDING", "model_execution": False,
             "metrics_exported": False, "full_pilot_approved": False, "execute_requested": execute,
             "hashes_only": hashes_only, "decode_validated": False}
    write_json(output / "status.json", state)
    try:
        inputs = FrozenPCBInputs(root, data_root)
        hashes = {name: file_sha256(root / name) for name in CODE}
        single_board_plan = 64 * max(p.size_wh[0] * p.size_wh[1] for p in inputs.parents)
        protocol = {"kind": KIND, "input_kind": "actual_files_structural_audit_not_predictions",
            "data_root": str(inputs.data_root), "references_sha256": inputs.references,
            "official_csv_sha256": inputs.official_sha256, "geometry_id": inputs.geometry_id,
            "partitions": PARTITIONS, "source_sha256": hashes,
            "decode_single_board_array_payload_plan_bytes": single_board_plan,
            "decode_fixed_ram_reserve_bytes": RAM_RESERVE,
            "available_ram_bytes_at_protocol_snapshot": available_ram(),
            "memory_scope": "decode plan only; hashes-only uses the existing streamed file hasher, no native arrays",
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_worktree_dirty": bool(subprocess.check_output(
                ["git", "status", "--porcelain", "--ignore-submodules=all"], cwd=root, text=True).strip()),
            "resize_pad_dilate_or_exclude": False, "model_or_anomaly_metric_execution": False,
            "scope": "streamed source hashes only; no RGB/GT decoding" if hashes_only else
                     "sequential RGB verification, then native test-GT evaluation-input verification only"}
        write_json(output / "PROTOCOL.json", protocol)
        state["protocol_sha256"] = file_sha256(output / "PROTOCOL.json")
        if execute and hashes_only:
            start = perf_counter()
            rgb = [_hash_receipt(inputs, parent) for parent in inputs.parents]
            _csv(output / "rgb_binding.csv", rgb)
            gt = [_hash_receipt(inputs, parent, gt=True) for parent in inputs.parents if parent.split == "test"]
            _csv(output / "gt_binding.csv", gt)
            state.update(source_hash_verification_seconds=perf_counter() - start,
                rgb_hash_count=len(rgb), test_mask_hash_count=len(gt),
                actual_mask_files=sum(p.label for p in inputs.parents if p.split == "test"),
                receipt_sha256={name: file_sha256(output / name) for name in ("rgb_binding.csv", "gt_binding.csv")})
        elif execute:
            start = perf_counter()
            for parent in inputs.parents:
                _budget(64 * parent.size_wh[0] * parent.size_wh[1], None)
                values = inputs.rgb(parent)
                del values
            state["rgb_verification_seconds"] = perf_counter() - start
            _csv(output / "rgb_binding.csv", list(inputs.rgb_receipts.values()))
            state["phase"] = "native_test_gt_input_audit"
            write_json(output / "status.json", state)
            from .evaluation import connected_components
            start, region_payload = perf_counter(), 0
            for parent in inputs.parents:
                if parent.split != "test":
                    continue
                _budget(64 * parent.size_wh[0] * parent.size_wh[1], None)
                mask = inputs.evaluation_mask(parent)
                regions = int(connected_components(mask, connectivity=1).max())
                inputs.gt_receipts[parent.sample].update(four_connected_regions=regions,
                                                         anomaly_pixels=int(mask.sum()))
                region_payload += regions * mask.size
                del mask
            state["gt_verification_seconds"] = perf_counter() - start
            _csv(output / "gt_binding.csv", list(inputs.gt_receipts.values()))
            state.update(rgb_count=len(inputs.rgb_receipts), test_mask_count=len(inputs.gt_receipts),
                decode_validated=True,
                actual_mask_files=sum(p.label for p in inputs.parents if p.split == "test"),
                four_connected_region_mask_payload_bytes=region_payload,
                receipt_sha256={name: file_sha256(output / name) for name in ("rgb_binding.csv", "gt_binding.csv")})
        inputs.verify_references()
        if hashes != {name: file_sha256(root / name) for name in CODE}:
            raise ValueError("Audit sources changed during verification")
        state["status"] = ("FILE_HASHES_VALIDATED_DECODE_PENDING_NOT_FULL_APPROVAL" if hashes_only else
                           "INPUT_BINDING_VALIDATED_NOT_FULL_APPROVAL" if execute else "PREFLIGHT_PASS")
        write_json(output / "status.json", state)
        return state, output
    except BaseException as error:
        state.update(status="BLOCKED_MEMORY" if isinstance(error, MemoryError) else "FAILED",
                     error=f"{type(error).__name__}: {error}")
        write_json(output / "status.json", state)
        raise
