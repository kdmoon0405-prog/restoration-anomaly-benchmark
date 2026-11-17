"""Export one completed bank-domain producer run into the CPU consumer's five-file contract.

Input: a producer run directory (status.json, raw_<bank>.npz, test_masks_for_local_analysis.npz, summary.csv,
per_image.csv, query_quality.csv) from scripts/run_bank_domain_study.py. Output (new directory):
bank_domain_manifest.json, config.json, provenance.json, summary.csv, per_image.csv
(docs/BANK_DOMAIN_ANALYSIS_HANDOFF.md). Producer files are only read.

Added by the takeover (not part of the producer patch):
- roi_bg_gap: mean(ROI) - mean(background) of the cell-normalized map (that cell's normal-calibration median/IQR),
  so gaps are on a comparable scale across banks; GT is used only for this post-hoc evaluation.
- source_commit is the commit given with --source-commit, accepted only if every listed code file is byte-identical
  to that commit (the producer records branch and dirty flag but not the commit hash).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sr_anomaly import bank_domain_study as study  # noqa: E402
from sr_anomaly.fusion import normalize  # noqa: E402

CODE_FILES = ("scripts/run_bank_domain_study.py", "src/sr_anomaly/bank_domain_study.py", "scripts/run_fusion_patchcore.py",
              "src/sr_anomaly/fusion.py", "src/sr_anomaly/evaluation.py", "src/sr_anomaly/real_models.py",
              "src/sr_anomaly/metrics.py", "src/sr_anomaly/dataset.py")
METRIC_DEFINITION = dict(primary="pooled_aupro", max_fpr=0.3, num_thresholds=200, connectivity=4)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(value) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, data: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def code_digests(commit: str) -> dict:
    out = {}
    for name in CODE_FILES:
        current = (ROOT / name).read_bytes()
        at_commit = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{name}"], capture_output=True, check=True).stdout
        if current != at_commit and current.replace(b"\r\n", b"\n") != at_commit.replace(b"\r\n", b"\n"):
            raise ValueError(f"{name} differs from {commit}; cannot attribute the run to that commit")
        out[name] = sha(current)
    return out


def export(run_dir: Path, output: Path, source_commit: str, family: str = "patchcore_bank_domain_v1") -> dict:
    run_dir, output = Path(run_dir), Path(output)
    if output.exists():
        raise FileExistsError(f"{output} exists; exports are never overwritten")
    state = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    status = state.get("status")
    recorded = state.get("source_commit")
    source_commit = source_commit or recorded
    if not source_commit:
        raise ValueError("no source commit recorded by the producer and none given")
    full = subprocess.run(["git", "-C", str(ROOT), "rev-parse", source_commit], capture_output=True, text=True, check=True).stdout.strip()
    if recorded and recorded != full:
        raise ValueError(f"given commit {full} differs from the producer's recorded {recorded}")
    output.mkdir(parents=True)
    if status != "COMPLETE":
        manifest = dict(schema_version=1, kind="bank_domain_study_results", status="FAILED" if status == "FAILED" else "PARTIAL",
                        evidence_kind="model_predictions", files={}, producer_status=status, producer_error=state.get("error"))
        (output / "bank_domain_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        return manifest
    category, seed = state["category"], int(state["seed"])
    tests = list(state["test_samples"])
    quality = {r["sample"]: r for r in rows(run_dir / "query_quality.csv")}
    masks_npz = np.load(run_dir / "test_masks_for_local_analysis.npz")
    if [str(s) for s in masks_npz["samples"]] != tests:
        raise ValueError("mask sample order differs from the run's test order")
    masks = masks_npz["masks"].astype(bool)
    producer_rows = rows(run_dir / "per_image.csv")
    producer_summary = rows(run_dir / "summary.csv")
    raw = {b: np.load(run_dir / f"raw_{b}.npz") for b in study.BANK_DOMAINS}
    labels = {r["sample"]: int(r["label"]) for r in producer_rows}
    defect = {r["sample"]: r["defect_type"] for r in producer_rows}
    summary, per_image = [], []
    for bank in study.BANK_DOMAINS:
        values = raw[bank]
        for qi, query in enumerate(study.QUERY_DOMAINS):
            cal = state["calibration_by_cell"][f"{bank}/{query}"]
            maps = normalize(values["test_maps"][:, qi], cal["pixel"])
            src = next(r for r in producer_summary if r["bank_domain"] == bank and r["query_domain"] == query)
            q = "bicubic" if query == "bicubic_x4" else "swinir"
            psnr = [float(quality[s][f"psnr_{q}"]) for s in tests]
            ssim = [float(quality[s][f"ssim_{q}"]) for s in tests]
            summary.append(dict(bank_domain=bank, query_domain=query, n_test=len(tests), n_anomaly=sum(labels[s] for s in tests),
                                pooled_aupro=float(src["pooled_aupro_at_0_3"]), pixel_auroc=float(src["pixel_auroc"]),
                                image_auroc=float(src["image_auroc"]), mean_psnr=float(np.mean(psnr)), mean_ssim=float(np.mean(ssim)),
                                image_f1=src["image_f1"], image_threshold=src["image_threshold"], pixel_threshold=src["pixel_threshold"]))
            prod = {r["sample"]: r for r in producer_rows if r["bank_domain"] == bank and r["query_domain"] == query}
            for i, s in enumerate(tests):
                anomalous = labels[s] == 1
                gap = float(maps[i][masks[i]].mean() - maps[i][~masks[i]].mean()) if anomalous else ""
                aupro = prod[s].get("per_image_aupro", "") if anomalous else ""
                per_image.append(dict(sample=s, defect_type=defect[s], label=labels[s], bank_domain=bank, query_domain=query,
                                      per_image_aupro=aupro, roi_bg_gap=gap, psnr=quality[s][f"psnr_{q}"], ssim=quality[s][f"ssim_{q}"],
                                      normalized_score=prod[s]["normalized_score"]))
    write_csv(output / "summary.csv", summary)
    write_csv(output / "per_image.csv", per_image)
    proto_src = state.get("model_configuration", {})
    checkpoints = {k: v for k, v in dict(swinir_x4=proto_src.get("swinir_checkpoint_sha256"),
                                          wide_resnet50_2=proto_src.get("backbone_checkpoint_sha256")).items() if v}
    config = dict(study_family=family, category=category, seed=seed, protocol=dict(
        dataset="MVTecAD", geometry_id="resize256_bilinear_centercrop224", degradation_id="bicubic_x0.25_to_56_then_x4",
        detector_id="patchcore_wrn50_layer2_3_identity_sampler_exact_faiss_k1", restorer_id="swinir_lightweight_x4_tile56",
        bank_spec=dict(layers=["layer2", "layer3"], embedding_dim=1024, patches_per_image=784, sampler="IdentitySampler",
                       fit_fraction=0.8, fit_count=state["fit_count"]),
        checkpoints_sha256=checkpoints, calibration_source="normal_calibration_only", metric_definition=METRIC_DEFINITION,
        roi_bg_gap_definition="mean ROI minus mean background of the cell-normalized map (normal-calibration median/IQR)"))
    (output / "config.json").write_text(json.dumps(config, indent=1), encoding="utf-8")
    bicubic_sha = {b: [str(x) for x in raw[b]["query_bicubic_sha256"]] for b in study.BANK_DOMAINS}
    swinir_sha = {b: [str(x) for x in raw[b]["query_swinir_sha256"]] for b in study.BANK_DOMAINS}
    if bicubic_sha["clean"] != bicubic_sha["swinir_restored"] or swinir_sha["clean"] != swinir_sha["swinir_restored"]:
        raise ValueError("query RGB hashes differ between banks")
    vectors = {r["bank_domain"]: int(r["bank_bytes"]) // (1024 * 4) for r in state["runtime"]}
    provenance = dict(
        source_commit=full, source_worktree_dirty=bool(state.get("git_dirty")), source_branch=state.get("git_branch"),
        code_sha256=code_digests(full), normal_fit_calibration_disjoint=not set(state["fit_paths"]) & set(state["calibration_paths"]),
        test_gt_used_for_selection=False,
        input_manifest_sha256=canonical_sha(dict(query_input_sha256=[str(x) for x in raw["clean"]["query_input_sha256"]],
                                                 dataset_provenance=state["dataset_provenance"])),
        split_manifest_sha256=canonical_sha(dict(fit=state["fit_paths"], calibration=state["calibration_paths"])),
        test_manifest_sha256=canonical_sha(dict(samples=tests, masks=state["test_mask_sha256"])),
        query_manifest_sha256=canonical_sha(dict(bicubic_x4=bicubic_sha["clean"], swinir_x4=swinir_sha["clean"])),
        bank_manifest_sha256=dict(state["bank_hashes"]), bank_manifest_kind="sha256 of the float32 bank vector array",
        bank_vector_counts=vectors, submodule_revisions=state.get("submodule_revisions"),
        producer_run=dict(run_id=state["run_id"], status_sha256=sha((run_dir / "status.json").read_bytes()),
                          artifacts=state.get("artifacts")),
        exporter="scripts/export_bank_domain_contract.py", exporter_sha256=sha(Path(__file__).read_bytes()))
    if not provenance["normal_fit_calibration_disjoint"]:
        raise ValueError("fit and calibration overlap")
    (output / "provenance.json").write_text(json.dumps(provenance, indent=1), encoding="utf-8")
    files = {n: sha((output / n).read_bytes()) for n in ("summary.csv", "per_image.csv", "config.json", "provenance.json")}
    manifest = dict(schema_version=1, kind="bank_domain_study_results", status="COMPLETE", evidence_kind="model_predictions", files=files)
    (output / "bank_domain_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-commit", help="defaults to the commit recorded in the producer status.json")
    a = p.parse_args(argv)
    print(json.dumps(export(a.run, a.output, a.source_commit), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
