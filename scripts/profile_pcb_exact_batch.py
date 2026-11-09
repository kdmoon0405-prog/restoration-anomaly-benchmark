"""Small exact-search batch comparison on FIXED PCB queries (one axis: query tiles per search call, {1, 2, 4}).

Kept fixed: the reviewed real bank (hash-verified, not refit), the upstream scorer bind (CPU IndexFlatL2 exact,
k=1, squared L2), 4 FAISS threads, and one set of query embeddings reused by every condition.
Query tiles are fixed by inventory order and tile ordinal only (no GT, no scores):
    first calibration board tiles 0-2, first test board tiles 0-2 (clean variant, native 224 tiles).
Embedding/extraction cost is timed separately from search. Warmup 1 pass per condition, then 3 measured
passes with the condition order rotated each round. No condition is added. GPU FAISS / approximate search /
bank or coreset changes are out of scope.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import json
import platform
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BATCH_TILES = (1, 2, 4)
ROUNDS = 3
TILES_PER_BOARD = 3
OS_RESERVE = 2 * 1024**3          # technical headroom, same constant as the postprocess guard
MODEL_RUNTIME_SCENARIO = 2 * 1024**3  # same scenario term as the bank-fit plan
FAISS_BLOCK_QUERIES, FAISS_BLOCK_DB = 4096, 1024  # IndexFlatL2 BLAS blocking (exhaustive_L2sqr_blas defaults)


# ---------- pure helpers (unit-tested) ----------
def fixed_query_plan(parents, tiles_per_board=TILES_PER_BOARD):
    """First calibration and first test parent in frozen inventory order; tiles 0..n-1. GT/score free."""
    plan = []
    for split in ("calibration", "test"):
        parent = next(p for p in parents if p.split == split)
        plan += [dict(sample=parent.sample, split=split, tile_id=t) for t in range(tiles_per_board)]
    return plan


def batches(n, size):
    return [list(range(i, min(i + size, n))) for i in range(0, n, size)]


def condition_order(round_index, conditions=BATCH_TILES):
    k = round_index % len(conditions)
    return list(conditions[k:]) + list(conditions[:k])


def scratch_estimate(queries, db, dim, k=1):
    """Estimated transient search bytes: query copy + IP block + norms + outputs (estimate, not measured)."""
    block = min(queries, FAISS_BLOCK_QUERIES) * min(db, FAISS_BLOCK_DB) * 4
    return dict(query_copy_bytes=queries * dim * 4, ip_block_bytes=block, norms_bytes=(queries + min(db, FAISS_BLOCK_DB)) * 4,
                output_bytes=queries * k * (4 + 8))


def ram_preflight(bank_bytes, query_tiles, patches, dim, db, available, conditions=BATCH_TILES):
    """Bank mmap + scorer merged copy + index storage + model scenario + all fixed queries + per-condition scratch
    with a concurrent second query copy + OS reserve. A condition that does not fit is BLOCKED_MEMORY."""
    base = dict(bank_mmap_resident_bytes=bank_bytes, scorer_merged_copy_bytes=bank_bytes, faiss_index_storage_bytes=bank_bytes,
                model_runtime_scenario_bytes=MODEL_RUNTIME_SCENARIO, fixed_queries_bytes=query_tiles * patches * dim * 4,
                os_reserve_bytes=OS_RESERVE)
    rows = []
    for b in conditions:
        s = scratch_estimate(b * patches, db, dim)
        need = sum(base.values()) + sum(s.values()) + s["query_copy_bytes"]  # concurrent copy
        rows.append(dict(batch_tiles=b, queries_per_call=b * patches, required_bytes=need, available_bytes=available,
                         status="PASS" if need <= available else "BLOCKED_MEMORY", **s))
    return base, rows


def run_schedule(search, queries, conditions=BATCH_TILES, rounds=ROUNDS, clock=time.perf_counter, on_call=None):
    """queries: [n_tiles, patches, dim]. Returns outputs per condition (from the first measured pass) and timings."""
    n = len(queries)
    outputs, calls, passes = {}, [], []

    def one_pass(b, phase, round_index):
        d_parts, i_parts, total = [], [], 0.0
        for call_index, group in enumerate(batches(n, b)):
            q = np.ascontiguousarray(queries[group].reshape(-1, queries.shape[-1]))
            t0 = clock(); d, i = search(q); t1 = clock()
            total += t1 - t0
            calls.append(dict(phase=phase, round=round_index, batch_tiles=b, call=call_index, tiles=len(group),
                              queries=len(q), search_seconds=t1 - t0, **(on_call() if on_call else {})))
            d_parts.append(np.asarray(d).reshape(len(group), -1, d.shape[-1]))
            i_parts.append(np.asarray(i).reshape(len(group), -1, i.shape[-1]))
        passes.append(dict(phase=phase, round=round_index, batch_tiles=b, calls=len(batches(n, b)), pass_search_seconds=total))
        return np.concatenate(d_parts), np.concatenate(i_parts)

    for b in conditions:
        one_pass(b, "warmup", -1)
    for r in range(rounds):
        for b in condition_order(r, conditions):
            d, i = one_pass(b, "measured", r)
            if b not in outputs:
                outputs[b] = (d, i)
            else:  # repeat determinism inside a condition
                if not (np.array_equal(outputs[b][0], d) and np.array_equal(outputs[b][1], i)):
                    outputs[b] = outputs[b] + ("NONDETERMINISTIC_REPEAT",)
    return outputs, calls, passes


def compare(base, other, downstream, rtol=1e-5, atol=1e-6):
    """base/other: (D[tiles,patches,k], I[...]). downstream(D_tile)->(score, map)."""
    (bd, bi), (od, oi) = base[:2], other[:2]
    diff = np.abs(od.astype(np.float64) - bd)
    idx_diff = bi != oi
    tie_ok = bool(np.allclose(od[idx_diff], bd[idx_diff], rtol=rtol, atol=atol)) if idx_diff.any() else True
    s_diff, m_max, m_mean = [], [], []
    for t in range(len(bd)):
        bs, bm = downstream(bd[t]); os_, om = downstream(od[t])
        s_diff.append(abs(os_ - bs)); md = np.abs(om.astype(np.float64) - bm)
        m_max.append(md.max()); m_mean.append(md.mean())
    return dict(distance_max_abs_diff=float(diff.max()), distance_mean_abs_diff=float(diff.mean()),
                distance_allclose=bool(np.allclose(od, bd, rtol=rtol, atol=atol)), distance_bitwise_equal=bool(np.array_equal(od, bd)),
                nn_index_differences=int(idx_diff.sum()), nn_index_differences_distance_tied=tie_ok,
                score_max_abs_diff=float(max(s_diff)), map_max_abs_diff=float(max(m_max)), map_mean_abs_diff=float(np.mean(m_mean)),
                rtol=rtol, atol=atol)


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "x", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fields); w.writeheader(); w.writerows(rows)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def board_recheck(raw_run, parents, adapter, geometry, variants=("clean", "swinir_x4")):
    """Diagnosis only (not part of the batch timing): first test board in inventory order, stored prepared RGB tiles
    (no SR rerun), same bound index. Checks board score == max(tile scores) and overlap-mean map vs the stored map."""
    sys.path.insert(0, str(ROOT / "src"))
    from sr_anomaly.tiled_cpu_pipeline import TilePrediction, assemble_board
    manifest = list(csv.DictReader(open(raw_run / "units_manifest.csv", encoding="utf-8")))
    parent = next(p for p in parents if p.split == "test")
    rows = []
    for v in variants:
        m = next(r for r in manifest if r["sample"] == parent.sample and r["variant"] == v)
        unit = json.loads((raw_run / "units" / f"{int(m['index']):04d}.json").read_text(encoding="utf-8"))
        spool_name = next(k for k in unit["files"] if k.startswith("rgb/tiles-"))
        if _sha(raw_run / spool_name) != unit["files"][spool_name]["sha256"]:
            raise ValueError("Spool checksum mismatch")
        spool = np.load(raw_run / spool_name, mmap_mode="r")
        boxes = geometry.tile_boxes(parent.size_wh)
        preds, t0 = [], time.perf_counter()
        for t, box in enumerate(boxes):
            amap, score = adapter.predict(np.ascontiguousarray(spool[t]))
            preds.append(TilePrediction(parent.sample, v, t, box, amap, score))
        seconds = time.perf_counter() - t0
        b = assemble_board(parent.sample, v, parent.size_wh, iter(preds))
        stored = np.load(raw_run / m["file"], mmap_mode="r")
        tile_scores = np.array([p.score for p in preds])
        d = np.abs(np.asarray(stored, np.float64) - b.anomaly_map)
        rows.append(dict(sample=parent.sample, variant=v, stored_score=float(m["score"]), recomputed_board_score=b.score,
                         recomputed_equals_max_tile=bool(b.score == tile_scores.max()), argmax_tile=int(tile_scores.argmax()),
                         score_abs_diff=abs(b.score - float(m["score"])), map_max_abs_diff=float(d.max()), map_mean_abs_diff=float(d.mean()),
                         stored_map_max=float(np.max(stored)), tile_score_max_over_tile_map_max=float(tile_scores.max() / max(p.anomaly_map.max() for p in preds)),
                         spool=spool_name, predict_seconds=seconds, note="separate diagnosis; not a re-run of the cohort"))
    return rows


# ---------- real execution ----------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-run", type=Path, default=ROOT / "outputs/pcb-full-cohort/pcb-full-cohort-20261101-a")
    ap.add_argument("--bank-run", type=Path, default=ROOT / "outputs/pcb-fit-bank/pcb-real-fit-bank-20261029-163524")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data/external/VisA")
    ap.add_argument("--output", type=Path, required=True, help="public CSV/JSON (no arrays)")
    ap.add_argument("--array-dir", type=Path, required=True, help="local-only fixed query/distances (gitignored)")
    ap.add_argument("--rtol", type=float, default=1e-5)
    ap.add_argument("--atol", type=float, default=1e-6)
    ap.add_argument("--board-recheck", action="store_true",
                    help="separate diagnosis: re-predict the first test board (clean, swinir_x4) from its stored RGB spool")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "src"))
    from sr_anomaly import bounded_bank as bank
    from sr_anomaly import pcb_board_analysis as board
    from sr_anomaly import pcb_fit_bank as fit
    from sr_anomaly import pcb_tiling as geometry
    from sr_anomaly.pcb_native_memory import process_memory
    from sr_anomaly.pcb_tiled_runner import available_ram
    for d in (args.output, args.array_dir):
        d.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((args.raw_run / "PROTOCOL.json").read_text(encoding="utf-8"))
    _, parents = board.load_raw_run(args.raw_run)
    plan = fixed_query_plan(parents)
    record = dict(kind="pcb_exact_search_batch_comparison", axis="query tiles per search call", conditions=list(BATCH_TILES),
                  rounds=ROUNDS, warmup_passes_per_condition=1, order_rotation=[condition_order(r) for r in range(ROUNDS)],
                  query_plan=plan, variant="clean", raw_run=str(args.raw_run), raw_status_sha256=_sha(args.raw_run / "status.json"),
                  raw_execution_family=protocol["execution_family"], bank_run=str(args.bank_run),
                  start=time.strftime("%Y-%m-%dT%H:%M:%S%z"), python=sys.version, platform=platform.platform(),
                  argv=sys.argv, rtol=args.rtol, atol=args.atol)
    # Bank + inputs (verified) before any model allocation.
    values, indices, _ = bank.load_complete_bank(args.bank_run / "bank")
    record["bank_sha256"] = {n: _sha(args.bank_run / "bank" / n) for n in ("bank.npy", "selected_indices.npy")}
    record["bank_matches_raw_admission"] = record["bank_sha256"]["bank.npy"] == protocol["bank_admission"]["file_sha256"]["bank/bank.npy"]
    if not record["bank_matches_raw_admission"]:
        raise ValueError("Bank differs from the raw run admission")
    available = available_ram()
    base, pre = ram_preflight(values.nbytes, len(plan), 784, values.shape[1], len(values), available)
    record.update(preflight_base=base, preflight_available_at_start=available)
    write_csv(args.output / "ram_preflight.csv", pre)
    runnable = tuple(r["batch_tiles"] for r in pre if r["status"] == "PASS")
    if not runnable:
        record.update(status="BLOCKED_MEMORY"); (args.output / "RECORD.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        return 2
    inputs = fit.binding.FrozenPCBInputs(ROOT, args.data_root)
    ck = protocol["checkpoints"]
    import faiss
    import torch
    adapter, _transform = fit.models.create_models(ROOT, "cuda", ck["backbone"]["path"], ck["swinir"]["path"])
    by_sample = {p.sample: p for p in parents}
    tiles, t_extract = [], 0.0
    for sample in dict.fromkeys(q["sample"] for q in plan):
        rgb = inputs.rgb(by_sample[sample])
        boxes = geometry.tile_boxes(by_sample[sample].size_wh)
        native = list(geometry.extract_tiles(rgb, boxes))
        tiles += [np.ascontiguousarray(native[q["tile_id"]]) for q in plan if q["sample"] == sample]
    feats = []
    for t in tiles:
        t0 = time.perf_counter(); f = adapter.extract(t[None]); torch.cuda.synchronize(); t_extract += time.perf_counter() - t0
        feats.append(f.reshape(-1, f.shape[-1]))
    queries = np.stack(feats).astype(np.float32)
    np.save(args.array_dir / "fixed_queries.npy", queries, allow_pickle=False)
    record.update(query_shape=list(queries.shape), patches_per_tile=int(queries.shape[1]),
                  query_sha256=_sha(args.array_dir / "fixed_queries.npy"), extraction_seconds_total=t_extract,
                  extraction_note="CUDA backbone _embed; timed separately, excluded from search timing")
    rss_before_bind = process_memory()["rss_bytes"]
    t0 = time.perf_counter(); adapter.bind_bank(values); bind_seconds = time.perf_counter() - t0
    nn = adapter.model.anomaly_scorer.nn_method
    index = nn.search_index
    record.update(bind_seconds=bind_seconds, rss_before_bind=rss_before_bind, rss_after_bind=process_memory()["rss_bytes"],
                  index_type=type(index).__name__, index_ntotal=int(index.ntotal), faiss_version=faiss.__version__,
                  faiss_omp_threads=faiss.omp_get_max_threads(), metric="squared L2 (IndexFlatL2), k=1, mean over k")
    if record["faiss_omp_threads"] != 4 or "IndexFlatL2" not in record["index_type"]:
        raise ValueError("Execution family drift: expected CPU IndexFlatL2 with 4 threads")
    seg = adapter.model.anomaly_segmentor

    def downstream(d_tile):
        patch = d_tile.mean(-1).reshape(1, 28, 28)
        return float(patch.max()), np.asarray(seg.convert_to_segmentation(patch)[0], dtype=np.float32)

    # Path identity: our downstream on baseline distances must reproduce adapter.predict for the same tiles.
    peak = {"value": 0}
    stop = threading.Event()

    def sampler():
        while not stop.wait(.02):
            peak["value"] = max(peak["value"], process_memory()["rss_bytes"])
    th = threading.Thread(target=sampler, daemon=True); th.start()
    try:
        def on_call():
            m = process_memory()
            return dict(rss_after_call=m["rss_bytes"], sampled_peak_rss_so_far=max(peak["value"], m["rss_bytes"]),
                        wall_time=time.strftime("%H:%M:%S"))
        outputs, calls, passes = run_schedule(lambda q: nn.run(1, q), queries, conditions=runnable, on_call=on_call)
    finally:
        stop.set(); th.join()
    identity = []
    for t, tile in enumerate(tiles):
        m, s = adapter.predict(tile)
        bs, bm = downstream(outputs[runnable[0]][0][t])
        identity.append(dict(tile=t, sample=plan[t]["sample"], tile_id=plan[t]["tile_id"], predict_score=s, downstream_score=bs,
                             score_abs_diff=abs(s - bs), map_max_abs_diff=float(np.abs(m - bm).max())))
    write_csv(args.output / "path_identity_vs_predict.csv", identity)
    if args.board_recheck:
        recheck_rows = board_recheck(args.raw_run, parents, adapter, geometry)
        write_csv(args.output / "diagnostic_board_recheck.csv", recheck_rows)
    write_csv(args.output / "timing_calls.csv", calls)
    write_csv(args.output / "timing_passes.csv", passes)
    base_b = runnable[0]
    np.save(args.array_dir / f"distances_b{base_b}.npy", outputs[base_b][0], allow_pickle=False)
    eq, summary = [], []
    for b in runnable:
        row = dict(batch_tiles=b, baseline_batch_tiles=base_b, repeat_deterministic=len(outputs[b]) == 2,
                   **compare(outputs[base_b], outputs[b], downstream, args.rtol, args.atol))
        eq.append(row)
        m = np.array([p["pass_search_seconds"] for p in passes if p["batch_tiles"] == b and p["phase"] == "measured"])
        c = [x for x in calls if x["batch_tiles"] == b and x["phase"] == "measured"]
        pre_b = next(r for r in pre if r["batch_tiles"] == b)
        summary.append(dict(batch_tiles=b, queries_per_call=b * queries.shape[1], calls_per_pass=len(batches(len(queries), b)),
                            measured_passes=len(m), pass_seconds_mean=float(m.mean()), pass_seconds_min=float(m.min()),
                            pass_seconds_max=float(m.max()), seconds_per_tile_mean=float(m.mean() / len(queries)),
                            speedup_vs_b1_mean=float(np.mean([p["pass_search_seconds"] for p in passes if p["batch_tiles"] == 1 and p["phase"] == "measured"]) / m.mean()) if 1 in runnable else None,
                            measured_calls=len(c), scratch_estimate_bytes=sum(pre_b[k] for k in ("query_copy_bytes", "ip_block_bytes", "norms_bytes", "output_bytes")),
                            max_rss_after_call=max(x["rss_after_call"] for x in c), sampled_peak_rss=max(x["sampled_peak_rss_so_far"] for x in c)))
    write_csv(args.output / "equivalence.csv", eq)
    write_csv(args.output / "condition_summary.csv", summary)
    record.update(status="COMPLETE", runnable=list(runnable), blocked=[r["batch_tiles"] for r in pre if r["status"] != "PASS"],
                  end=time.strftime("%Y-%m-%dT%H:%M:%S%z"), process_memory_end=process_memory(),
                  thermal_note="CPU temperature not measured; per-call wall_time and per-round timings show drift only")
    (args.output / "RECORD.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    adapter.close()
    print(json.dumps(summary, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
