import numpy as np
from PIL import Image

from scripts.review_saved_evidence import crop_audit, timing_audit


def test_nonempty_mask_can_lose_whole_and_partial_defects():
    mask = np.zeros((256, 256), dtype=np.uint8)
    mask[:4, :4] = 255
    mask[40:44, 14:18] = 255
    mask[100:104, 100:104] = 255
    result = crop_audit(Image.fromarray(mask))
    assert not result["empty_after_crop"]
    assert result["components_before_crop"] == 3
    assert result["components_fully_removed"] == 1
    assert result["components_partially_cut"] == 1
    assert result["lost_defect_fraction"] == .5
    assert result["defect_pixels_after_crop"] == 24


def test_timing_parent_is_not_added_to_exclusive_children():
    row = {"phase": "instrumented", "variant": "degraded", "sample": "a", "repeat": "1",
           "backbone_embedding_seconds": "1", "feature_detach_cpu_numpy_seconds": ".1",
           "faiss_search_seconds": "8", "score_map_postprocessing_seconds": ".2",
           "detector_glue_seconds": ".7", "detector_total_seconds": "10"}
    stats, residual = timing_audit([row, {**row, "repeat": "2"}])
    group = stats["instrumented/degraded"]
    assert group["observations"] == 2 and group["unique_samples"] == 1 and group["repeats"] == 2
    assert residual < 1e-12
    assert group["detector_total_seconds"]["mean"] == 10
