"""One fixed balanced normal bank with unchanged capacity and patch locations."""
from pathlib import Path
import shutil
import time

import numpy as np

from .analysis_io import digest, new_output, read_json, write_json
from .cpu_hog_control import _guard
from .pcb_native_memory import process_memory


def construct_balanced_bank(bicubic, restored, output):
    bicubic, restored = Path(bicubic), Path(restored)
    a, b = (read_json(p / "status.json") for p in (bicubic, restored))
    if a["status"] != "BANK_COMPLETE" or b["status"] != "BANK_COMPLETE":
        raise ValueError("Both fitted normal banks must be complete")
    if (a["bank_domain"], b["bank_domain"]) != ("bicubic_matched", "swinir_restored"):
        raise ValueError("Expected Bicubic and restored normal banks")
    for field in ("category", "seed", "stored_vectors", "descriptor_dimension", "normal_fit_count",
                  "selected_indices_sha256", "split_sha256", "feature_source_sha256"):
        if a[field] != b[field]:
            raise ValueError("Normal bank source/split/ordinal mismatch: " + field)
    count = a["stored_vectors"]
    if count % 2 or a["descriptor_dimension"] != 36:
        raise ValueError("The fixed 50:50 HOG bank needs an even capacity and dimension36")
    for directory, state in ((bicubic, a), (restored, b)):
        if (digest(directory / "bank.npy") != state["bank_sha256"]
                or digest(directory / "selected_indices.npy") != state["selected_indices_sha256"]):
            raise ValueError("Fitted source bank changed")
    _guard(268435456 + count * 36 * 4 * 3, "Balanced CPU reference bank")
    out = new_output(Path(output), [bicubic, restored])
    tick = time.perf_counter()
    assignment = np.ones(count, dtype=np.uint8)
    selected = np.random.default_rng(np.random.SeedSequence([a["seed"], 20261109])).permutation(count)[:count // 2]
    assignment[selected] = 0
    with open(bicubic / "bank.npy", "rb") as first, open(restored / "bank.npy", "rb") as second:
        values_a, values_b = np.load(first, allow_pickle=False), np.load(second, allow_pickle=False)
    if values_a.shape != (count, 36) or values_b.shape != values_a.shape:
        raise ValueError("Unexpected source bank shape")
    values = np.where(assignment[:, None] == 0, values_a, values_b).astype(np.float32)
    if not np.isfinite(values).all():
        raise ValueError("Balanced reference contains non-finite features")
    np.save(out / "bank.npy", values, allow_pickle=False)
    np.save(out / "domain_assignment.npy", assignment, allow_pickle=False)
    shutil.copyfile(bicubic / "selected_indices.npy", out / "selected_indices.npy")
    state = dict(a, kind="cpu_hog_fixed_balanced_bank", bank_domain="balanced_mixed", device="cpu",
        bank_sha256=digest(out / "bank.npy"), construction_source_sha256=digest(Path(__file__)),
        source_bank_sha256=dict(bicubic=a["bank_sha256"], swinir=b["bank_sha256"]),
        bicubic_vectors=count // 2, swinir_vectors=count // 2,
        assignment_sha256=digest(out / "domain_assignment.npy"),
        assignment_policy="seed plus20261109, uniform balanced assignment to existing patch ordinals",
        construction_seconds=time.perf_counter() - tick, construction_process_memory=process_memory())
    write_json(out / "status.json", state)
    return state
