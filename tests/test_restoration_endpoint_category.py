"""Screw wrapper: frozen helpers reused; only direction comparison and case rule are new."""
from scripts import analyze_restoration_endpoint_category as cat


def _analysis(sign, case):
    methods = [{"variant": v, **{k: 0.5 for k in cat.COMPARED}} for v in ("bicubic_x4", "swinir_x4", "rrdb_psnr_x4")]
    methods.append({"variant": "rrdb_esrgan_x4", **{k: 0.5 + sign * 0.1 for k in cat.COMPARED}})
    return {"aggregate_methods": methods, "direct_per_image_aupro": {"mean": sign * 0.01}, "localization_case": case}


def test_direction_rows_agree_and_disagree():
    same = cat.compare_hazelnut(_analysis(1, "B"), _analysis(1, "B"))
    assert len(same) == len(cat.COMPARED) + 2 and all(r["direction"] == "agree" for r in same)
    opposite = cat.compare_hazelnut(_analysis(-1, "C"), _analysis(1, "A"))
    assert all(r["direction"] == "disagree" for r in opposite)


def test_screw_manifest_is_frozen_constant():
    assert cat.SCREW_MANIFEST[1:] == ("b680d6714fd9e1ca222ef4a5192478fd970c0b2dc70c5672d9c7aeb7e2bd51ec", 160, 41, 119)
