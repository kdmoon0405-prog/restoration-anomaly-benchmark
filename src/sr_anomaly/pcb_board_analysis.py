"""Board-level postprocessing, exact existing metrics, bounded phase lifetimes."""
from __future__ import annotations

import json
from numbers import Integral
from pathlib import Path
import shutil

import numpy as np

from .bounded_bank import _status, file_sha256
from .fusion import normalize, quantile_threshold, robust_params
from .pcb_tiled_models import VARIANTS, assemble_rgb
from .tiled_cpu_pipeline import Parent, validate_parents

RULE_ID = "pcb_board_robust_after_mean_v0_6"
QUANTILE = .99
RAM_RESERVE = 2 * 1024**3  # Fixed technical OS/runtime headroom, not a research threshold.


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _complete(directory, kind=None):
    state = _json(Path(directory)/"status.json")
    if state.get("status") != "COMPLETE" or (kind is not None and state.get("kind") != kind):
        raise ValueError("Incomplete or wrong artifact kind")
    return state


def _budget(required, budget, *, live_bytes=0, available_bytes=None):
    """Cap the TOTAL envelope + reserve; free RAM covers only its not-yet-live part.

    live_bytes is known allocated payload already included in required, never
    process RSS, mmap address space or another worker's peak. The cap includes
    the reserve and is not relaxed by live allocations.
    """
    from .pcb_tiled_runner import available_ram
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, Integral) or budget < 1):
        raise ValueError("Positive RAM budget bytes required")
    for name, value in (("required", required), ("live_bytes", live_bytes)):
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"Nonnegative integer {name} bytes required")
    if live_bytes > required:
        raise ValueError("Live bytes must be included in the phase envelope")
    available = available_ram() if available_bytes is None else available_bytes
    if isinstance(available, bool) or not isinstance(available, Integral) or available < 0:
        raise ValueError("Nonnegative integer available RAM bytes required")
    # Convert NumPy scalars before arithmetic to avoid fixed-width overflow.
    required, live_bytes, available = int(required), int(live_bytes), int(available)
    if budget is not None and required + RAM_RESERVE > int(budget):
        raise MemoryError("BLOCKED_MEMORY: fixed phase plan plus 2 GiB headroom exceeds RAM cap")
    if required - live_bytes + RAM_RESERVE > available:
        raise MemoryError("BLOCKED_MEMORY: insufficient available RAM including fixed 2 GiB headroom")


def _new_output(output, state, *, source_dirs=(), disk_bytes=0):
    output = Path(output).resolve()
    for source in source_dirs:
        source = Path(source).resolve()
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Output and source artifact trees must be disjoint")
    if output.exists():
        raise FileExistsError("Existing output is never overwritten")
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if disk_bytes > shutil.disk_usage(ancestor).free:
        raise OSError("Insufficient disk for planned output payload; overhead is additional")
    output.mkdir(parents=True, exist_ok=False)
    state.update(status="BUILDING", rule_id=RULE_ID)
    _status(output, state)
    return output


def _fail(output, state, error):
    state.update(status="FAILED", error=f"{type(error).__name__}: {error}")
    _status(output, state)


def load_raw_run(directory):
    """Validate inventory/bank provenance without reading test prediction values or GT."""
    directory = Path(directory)
    state = _complete(directory)
    parents = validate_parents(Parent(p["sample"], p["split"], p["label"], tuple(p["size_wh"])) for p in state["parents"])
    kind = state["provenance"].get("input_kind")
    if kind != "synthetic":
        # Real limited smoke must NEVER become a production calibration cohort.
        if kind != "fit_normal_feature_stream" or state.get("scope") != "full-pilot-raw":
            raise ValueError("Real smoke is not a full calibration/evaluation cohort")
        from .pcb_tiled_runner import GEOMETRY, load_inventory
        root = Path(__file__).resolve().parents[2]
        if parents != load_inventory(root/GEOMETRY)[0]:
            raise ValueError("Production requires exact frozen 721/180/200 parent inventory/order")
    hashes = state.get("bank_artifact_sha256", {})
    if set(hashes) != {"status.json", "bank.npy", "selected_indices.npy"} or not state.get("bank_unchanged"):
        raise ValueError("Missing immutable bank provenance")
    for name, digest in hashes.items():
        if file_sha256(directory/"bank"/name) != digest:
            raise ValueError("Raw bank artifact checksum mismatch")
    if _complete(directory/"bank")["provenance"] != state["provenance"]:
        raise ValueError("Bank/raw provenance mismatch")
    inventory = {p.sample: p for p in parents if p.split != "fit"}
    expected = {(p.sample, v) for p in inventory.values() for v in VARIANTS}
    observed = set()
    for i, row in enumerate(state["rows"]):
        key = row["sample"], row["variant"]
        p = inventory.get(row["sample"])
        if (key not in expected or key in observed or p is None or row["split"] != p.split
                or row["label"] != p.label or tuple(row["size_wh"]) != p.size_wh
                or row["file"] != f"predictions/{i:04d}.npy" or not np.isfinite(row["score"])):
            raise ValueError("Raw prediction inventory/split/label/path mismatch")
        observed.add(key)
    if observed != expected:
        raise ValueError("Missing raw predictions")
    return state, parents


def _map(directory, row, *, dtype=np.float32):
    path = Path(directory)/row["file"]
    if not path.resolve().is_relative_to(Path(directory).resolve()) or file_sha256(path) != row["sha256"]:
        raise ValueError("Prediction path/checksum mismatch")
    values = np.load(path, allow_pickle=False, mmap_mode="r")
    if values.shape != tuple(row["size_wh"])[::-1] or values.dtype != dtype or not np.isfinite(values).all():
        raise ValueError("Prediction shape/dtype/finite mismatch")
    return values


def memory_plan(parents, *, region_mask_bytes=None):
    parents = tuple(parents)
    pixels = {s: sum(p.size_wh[0]*p.size_wh[1] for p in parents if p.split == s)
              for s in ("calibration", "test")}
    largest = max(w*h for w,h in (p.size_wh for p in parents))
    cal, test = pixels["calibration"], pixels["test"]
    return {"calibration_pool_float64_bytes": 8*cal,
            "calibration_pool_plus_quantile_copy_scenario_bytes": 16*cal,
            "calibration_planning_envelope_bytes": 24*cal+32*largest,
            "normalized_test_files_bytes": 3*8*test,
            "evaluation_float64_stack_one_variant_bytes": 8*test,
            "evaluation_input_bool_masks_bytes": test,
            "evaluation_visible_pixel_auroc_scenario_bytes": 36*test,
            "evaluation_planning_envelope_bytes": 64*test+(region_mask_bytes or 0)+32*largest,
            "known_aupro_region_mask_bytes": region_mask_bytes,
            "quality_RGB_accumulator_coverage_output_bytes": (24+4+3+3)*largest,
            "quality_planning_envelope_bytes": 512*largest,
            "scope": "sequential variants; no model/index alive during postprocessing; no dataset-wide raw-map stack",
            "planning_not_RSS": True, "native_peak_validated": False,
            "formula": "calibration24Pcal+32Bmax; evaluator visible36Ptest; planning64Ptest+known region masks+32Bmax; quality512Bmax",
            "excluded": ["Python/runtime", "OS/page cache", "unvalidated library workspaces", "SSIM workspace beyond RGB payload"]}


def _fit_variant(directory, rows):
    """One pool; normalize it boardwise AFTER fitting, then exact existing quantile."""
    scores = np.asarray([r["score"] for r in rows], dtype=np.float64)
    image = robust_params(scores)
    total = sum(int(np.prod(r["size_wh"])) for r in rows)
    pool = np.empty(total, np.float64)
    offset = 0
    for row in rows:
        values = _map(directory, row)
        pool[offset:offset+values.size] = values.ravel()
        offset += values.size
        del values
    pixel = robust_params(pool)
    offset = 0
    for row in rows:
        size = int(np.prod(row["size_wh"]))
        pool[offset:offset+size] = normalize(pool[offset:offset+size], pixel)
        offset += size
    return {"image": image, "pixel": pixel,
            "image_threshold": quantile_threshold(normalize(scores, image), QUANTILE),
            "pixel_threshold": quantile_threshold(pool, QUANTILE),
            "normal_boards": len(rows), "pooled_pixels": total}


def fit_calibration(raw, output, *, ram_budget=None):
    source, parents = load_raw_run(raw)
    _budget(memory_plan(parents)["calibration_planning_envelope_bytes"], ram_budget)
    state = {"kind": "board_calibration", "raw_status_sha256": file_sha256(Path(raw)/"status.json"),
             "input_kind": source["provenance"]["input_kind"], "quantile": QUANTILE, "variants": {},
             "calibration_samples": [p.sample for p in parents if p.split == "calibration"]}
    output = _new_output(output, state, source_dirs=(raw,))
    try:
        for variant in VARIANTS:
            rows = [r for r in source["rows"] if r["split"] == "calibration" and r["variant"] == variant]
            params = _fit_variant(raw, rows)
            filename = f"{variant}.json"
            with (output/filename).open("x", encoding="utf-8") as handle:
                json.dump(params, handle, indent=2, allow_nan=False)
            state["variants"][variant] = {"file": filename, "sha256": file_sha256(output/filename)}
        state["status"] = "COMPLETE"
        _status(output, state)
    except BaseException as error:
        _fail(output, state, error)
        raise
    return state


def load_calibration(directory, raw):
    state = _complete(directory, "board_calibration")
    source = _complete(raw)
    calibration_parents = [p for p in source["parents"] if p["split"] == "calibration"]
    if (state.get("rule_id") != RULE_ID or state.get("quantile") != QUANTILE
            or state["raw_status_sha256"] != file_sha256(Path(raw)/"status.json")
            or set(state["variants"]) != set(VARIANTS)
            or state["calibration_samples"] != [p["sample"] for p in calibration_parents]):
        raise ValueError("Calibration rule/source/variant mismatch")
    params = {}
    for variant, entry in state["variants"].items():
        if entry["file"] != f"{variant}.json" or file_sha256(Path(directory)/entry["file"]) != entry["sha256"]:
            raise ValueError("Calibration checksum/path mismatch")
        values = _json(Path(directory)/entry["file"])
        if (values["normal_boards"] != len(calibration_parents)
                or values["pooled_pixels"] != sum(int(np.prod(p["size_wh"])) for p in calibration_parents)):
            raise ValueError("Wrong calibration cohort/pixel count")
        for domain in ("image", "pixel"):
            normalize(np.zeros(1), values[domain])  # Existing finite/positive-scale guards.
        if not all(np.isfinite(values[k]) for k in ("image_threshold", "pixel_threshold")):
            raise ValueError("Invalid calibration thresholds")
        params[variant] = values
    return state, params


def apply_calibration(raw, calibration, output, *, ram_budget=None):
    source, parents = load_raw_run(raw)
    _, params = load_calibration(calibration, raw)
    test_rows = [r for r in source["rows"] if r["split"] == "test"]
    _budget(max(np.prod(r["size_wh"]) for r in test_rows)*32, ram_budget)
    state = {"kind": "normalized_test", "raw_status_sha256": file_sha256(Path(raw)/"status.json"),
             "calibration_status_sha256": file_sha256(Path(calibration)/"status.json"), "rows": []}
    output = _new_output(output, state, source_dirs=(raw, calibration),
                         disk_bytes=memory_plan(parents)["normalized_test_files_bytes"])
    try:
        (output/"predictions").mkdir()
        for row in test_rows:
            values = _map(raw, row)
            fitted = params[row["variant"]]
            normalized = normalize(values, fitted["pixel"])
            filename = f"predictions/{len(state['rows']):04d}.npy"
            with (output/filename).open("xb") as handle:
                np.save(handle, normalized, allow_pickle=False)
            state["rows"].append(dict(row, file=filename, sha256=file_sha256(output/filename),
                score=float(normalize(np.asarray([row["score"]]), fitted["image"])[0])))
            del values, normalized
        state["status"] = "COMPLETE"
        _status(output, state)
    except BaseException as error:
        _fail(output, state, error)
        raise
    return state


def load_normalized(directory, raw, calibration):
    state = _complete(directory, "normalized_test")
    source, _ = load_raw_run(raw)
    if (state.get("rule_id") != RULE_ID or state["raw_status_sha256"] != file_sha256(Path(raw)/"status.json")
            or state["calibration_status_sha256"] != file_sha256(Path(calibration)/"status.json")):
        raise ValueError("Normalized source/calibration mismatch")
    expected = [(r["sample"], r["variant"], r["label"], r["size_wh"]) for r in source["rows"] if r["split"] == "test"]
    observed = [(r["sample"], r["variant"], r["label"], r["size_wh"]) for r in state["rows"]]
    if observed != expected or any(r["split"] != "test" or r["file"] != f"predictions/{i:04d}.npy"
                                   or not np.isfinite(r["score"]) for i,r in enumerate(state["rows"])):
        raise ValueError("Normalized test inventory mismatch")
    return state


def evaluate_variant(raw, calibration, normalized, variant, mask_loader, output, *, ram_budget=None):
    """GT is accepted ONLY here. No new metric implementation or resampling."""
    from .evaluation import connected_components, evaluate_predictions
    if variant not in VARIANTS:
        raise ValueError("Unknown variant")
    source, parents = load_raw_run(raw)
    _, params = load_calibration(calibration, raw)
    state = load_normalized(normalized, raw, calibration)
    plan = memory_plan(parents)
    _budget(plan["evaluation_planning_envelope_bytes"], ram_budget)
    rows = [r for r in state["rows"] if r["variant"] == variant]
    if len({tuple(r["size_wh"]) for r in rows}) != 1:
        raise ValueError("Existing evaluator needs matching native shapes; never resize/pad to pass")
    metadata = {"kind": "board_evaluation", "variant": variant, "input_kind": source["provenance"]["input_kind"],
                "normalized_status_sha256": file_sha256(Path(normalized)/"status.json"),
                "calibration_status_sha256": file_sha256(Path(calibration)/"status.json")}
    output = _new_output(output, metadata, source_dirs=(raw, calibration, normalized))
    try:
        maps = np.empty((len(rows), *rows[0]["size_wh"][::-1]), np.float64)
        masks = np.empty(maps.shape, bool)
        region_bytes = 0
        inventory = {p.sample:p for p in parents}
        for i,row in enumerate(rows):
            values = _map(normalized, row, dtype=np.float64)
            maps[i] = values
            del values
            mask = mask_loader(inventory[row["sample"]])
            if not isinstance(mask, np.ndarray) or mask.shape != masks.shape[1:] or not np.isin(mask, [0,1]).all():
                raise ValueError("GT native shape/binary mismatch")
            if bool(mask.any()) != bool(row["label"]):
                raise ValueError("GT and test label mismatch")
            masks[i] = mask
            region_bytes += int(connected_components(mask, connectivity=1).max())*mask.size
            del mask
        _budget(memory_plan(parents, region_mask_bytes=region_bytes)["evaluation_planning_envelope_bytes"],
                ram_budget, live_bytes=maps.nbytes + masks.nbytes)
        fitted = params[variant]
        metrics = evaluate_predictions(np.asarray([r["label"] for r in rows]), np.asarray([r["score"] for r in rows]),
            masks=masks, anomaly_maps=maps, image_threshold=fitted["image_threshold"],
            pixel_threshold=fitted["pixel_threshold"], max_fpr=.3)
        del maps, masks
        metadata.update(status="COMPLETE", metrics=metrics, aupro_region_mask_payload_bytes=region_bytes)
        _status(output, metadata)
    except BaseException as error:
        _fail(output, metadata, error)
        raise
    return metadata


def quality_report(parents, rgb_loader, variant_tiles, output, *, provenance, ram_budget=None):
    """Tiles must already be produced by the caller; this function runs NO restoration model."""
    from PIL import Image
    from .metrics import psnr, ssim
    parents = validate_parents(parents)
    _budget(memory_plan(parents)["quality_planning_envelope_bytes"], ram_budget)
    state = {"kind": "board_quality", "provenance": provenance, "rows": [], "summary": {}}
    output = _new_output(output, state)
    try:
        for parent in parents:
            if parent.split != "test":
                continue
            rgb = rgb_loader(parent)
            if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.shape != (*parent.size_wh[::-1],3):
                raise ValueError("Reference native RGB shape/dtype mismatch")
            reference = Image.fromarray(rgb)
            for variant in VARIANTS:
                reconstructed = Image.fromarray(assemble_rgb(parent.size_wh, variant_tiles(parent, variant)))
                score = psnr(reference, reconstructed)
                state["rows"].append({"sample": parent.sample, "variant": variant,
                    "psnr": score if np.isfinite(score) else "Infinity", "ssim": ssim(reference,reconstructed)})
                del reconstructed
            del reference, rgb
        for variant in VARIANTS:
            rows = [r for r in state["rows"] if r["variant"] == variant]
            mean_psnr = float(np.mean([float(r["psnr"]) for r in rows]))
            state["summary"][variant] = {"test_boards":len(rows),
                "mean_psnr":mean_psnr if np.isfinite(mean_psnr) else "Infinity",
                "mean_ssim":float(np.mean([r["ssim"] for r in rows]))}
        state["status"] = "COMPLETE"
        _status(output, state)
    except BaseException as error:
        _fail(output,state,error)
        raise
    return state
