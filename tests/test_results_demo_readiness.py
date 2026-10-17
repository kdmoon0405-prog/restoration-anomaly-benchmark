from io import BytesIO
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from threading import Thread
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image
import pytest

from scripts.check_pcb_readiness import choose_category
from scripts.serve_results_demo import StoredResults, handler_for


def test_read_only_panels_share_scale_and_gt_changes_only_rendering():
    state = StoredResults.__new__(StoredResults)
    state.paths = ["hazelnut/test/crack/000.png"]
    state.tau_deg, state.tau_rest = .5, .6
    mask = np.zeros((1, 4, 4), dtype=bool)
    mask[0, 1:3, 1:3] = True
    state.predictions = {name: {"maps": np.arange(16.).reshape(1, 4, 4)/16, "masks": mask.copy()}
                         for name in ("degraded_only", "restored_only", "candidate_1", "candidate_2")}
    state.sample = lambda index, variant: {"scale": {"vmin": 0., "vmax": 1.}}
    before = state.predictions["candidate_1"]["maps"].copy()
    plain = state.panel(0, "candidate_1")
    overlay = state.panel(0, "candidate_1", True)
    assert plain != overlay
    assert Image.open(BytesIO(plain)).size == (4, 4)
    np.testing.assert_array_equal(before, state.predictions["candidate_1"]["maps"])
    gate = state.panel(0, "gate_1")
    for item in state.predictions.values():
        item["masks"][:] = False
    assert state.panel(0, "gate_1") == gate
    with pytest.raises(ValueError):
        state.panel(-1, "candidate_1")
    with pytest.raises(ValueError):
        state.panel(0, "../../secret")
    assert hasattr(handler_for(state), "do_POST")


def test_pcb_choice_uses_completeness_count_lexical_and_trace_only():
    rows = [{"category": category, "raw_complete": True, "total_images": 100, "execution_traces": []}
            for category in ("pcb2", "pcb1")]
    assert choose_category(rows)["category"] == "pcb1"
    rows[0]["total_images"] = 99
    assert choose_category(rows)["category"] == "pcb2"
    rows[0]["execution_traces"] = ["outputs/old/results.json"]
    assert choose_category(rows)["category"] == "pcb1"
    rows[1]["raw_complete"] = False
    assert choose_category(rows) is None


def test_sample_uses_joint_map_scale_and_no_candidate_image_quality():
    state = StoredResults.__new__(StoredResults)
    sample = "hazelnut/test/good/000.png"
    state.paths = [sample]
    state.tau_deg, state.tau_rest = .5, .6
    state.predictions = {"degraded_only": {"maps": np.full((1, 2, 2), -2.)},
                         "restored_only": {"maps": np.full((1, 2, 2), 3.)},
                         "candidate_1": {"maps": np.zeros((1, 2, 2))}}
    state.per_image = {(sample, "candidate_1"): {"per_image_aupro": None}}
    state.quality = {sample: {"psnr_bicubic": 20., "psnr_swinir": 21., "ssim_bicubic": .7, "ssim_swinir": .8}}
    state.rgb_file = lambda index, kind: None
    data = state.sample(0, "candidate_1")
    assert data["scale"] == {"vmin": -2., "vmax": 3.}
    assert data["discrepancy_scale"] == {"vmin": 0., "vmax": 0.}
    assert data["per_image"]["per_image_aupro"] is None
    assert data["quality"] == state.quality[sample]
    assert not data["gate_uses_gt"] and not any(data["rgb_available"].values())
    assert "candidate" not in data["quality"]


def test_missing_artifacts_block_data_and_export_without_writes():
    state = StoredResults.__new__(StoredResults)
    state.unavailable = "Required saved predictions absent"
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/catalog", timeout=5) as response:
            assert json.load(response) == {"blocked": state.unavailable}
        with urlopen(base + "/favicon.ico", timeout=5) as response:
            assert response.status == 204
        for path in ("/api/sample", "/api/panel", "/export/summary.csv"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path, timeout=5)
            assert error.value.code == 503
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base, method="POST"), timeout=5)
        assert error.value.code == 405
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base, headers={"Host": "untrusted.example"}), timeout=5)
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
