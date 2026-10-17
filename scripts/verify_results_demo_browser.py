"""Optional real-browser check of the loopback saved-results viewer; no inference."""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"127.0.0.1", "localhost"}:
        parser.error("Local loopback viewer only")
    from playwright.sync_api import sync_playwright

    args.output.mkdir(parents=True, exist_ok=True)
    log_path = args.output / f"browser-{args.phase}.json"
    if log_path.exists():
        raise FileExistsError("Do not overwrite a recorded browser check")
    screenshots = args.output / "screenshots"
    screenshots.mkdir(exist_ok=True)
    errors, failed, http_errors, console_warnings, images = [], [], [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else (
            console_warnings.append(msg.text) if msg.type == "warning" else None))
        page.on("requestfailed", lambda req: failed.append({"url": req.url, "failure": req.failure}))
        page.on("response", lambda res: http_errors.append({"url": res.url, "status": res.status}) if res.status >= 400 else None)
        page.goto(args.url, wait_until="networkidle")
        catalog = context.request.get(args.url + "/api/catalog").json()
        assert len(catalog["samples"]) == 110 and len(catalog["variants"]) == 6
        assert page.locator("#sample option").count() == 110
        with (ROOT / catalog["analysis"] / "summary.csv").open(encoding="utf-8", newline="") as handle:
            original_summary = list(csv.DictReader(handle))
        assert [row["method"] for row in catalog["summary"]] == [row["method"] for row in original_summary]
        for row, original in zip(catalog["summary"], original_summary):
            for key, value in original.items():
                assert row[key] == (None if value == "" else value if key == "method" else float(value))
        per_image_path = ROOT / catalog["analysis"] / "per_image.csv"
        with per_image_path.open(encoding="utf-8", newline="") as handle:
            per_image = {(row["sample"], row["method"]): row for row in csv.DictReader(handle)}
        with (ROOT / catalog["source_run"] / "per_image.csv").open(encoding="utf-8", newline="") as handle:
            quality = {row["sample"]: row for row in csv.DictReader(handle)}

        def settled():
            page.wait_for_function("()=>Array.from(document.querySelectorAll('#panels img')).every(i=>i.complete&&i.naturalWidth>0)")
            assert "오류:" not in page.locator("#status").inner_text()

        def screenshot(name):
            settled()
            filename = screenshots / f"{args.phase}-{name}.png"
            page.screenshot(path=str(filename), full_page=True)
            images.append(filename.relative_to(args.output).as_posix())

        def choose(suffix, variant, overlay=False):
            sample = next(row for row in catalog["samples"] if row["sample"].endswith(suffix))
            page.locator("#defect").select_option(sample["defect_type"])
            page.locator("#sample").select_option(str(sample["index"]))
            page.locator("#variant").select_option(variant)
            page.locator("#overlay").set_checked(overlay)
            status = f"{sample['sample']} · {variant}"
            page.wait_for_function("expected=>document.getElementById('status').textContent===expected", arg=status)
            settled()
            data = context.request.get(f"{args.url}/api/sample?index={sample['index']}&variant={variant}").json()
            original = per_image[sample["sample"], variant]
            for key, value in data["per_image"].items():
                expected = original[key]
                if isinstance(value, (int, float)):
                    assert value == float(expected), (key, value, expected)
                else:
                    assert value == (expected or None)
            assert data["gate_uses_gt"] is False
            assert all(value == float(quality[sample["sample"]][key]) for key, value in data["quality"].items())
            metadata = json.loads(page.locator("#metadata").inner_text())
            assert metadata["baseline_quality"] == data["quality"]
            detail = page.locator("#detail").inner_text()
            if sample["label"] == 0:
                assert data["per_image"]["per_image_aupro"] is None and "해당 없음" in detail
            else:
                assert f"{data['per_image']['per_image_aupro']:.9f}" in detail
            for image in page.locator("#panels img").all():
                assert f"index={sample['index']}&" in image.get_attribute("src")
            return data

        screenshot("initial-restored")
        if args.phase == "after":
            assert page.locator("#colorbar").is_visible()
            assert "Discrepancy: 0 .." in page.locator("#discrepancy-scale").inner_text()
            assert "Pooled AU-PRO@0.3" in page.locator("#summary").inner_text()
        table_values = page.locator("#summary").inner_text()
        for row in catalog["summary"]:
            assert row["method"] in table_values and f"{row['pooled_au_pro']:.9f}" in table_values
        good = choose("good/000.png", "degraded_only")
        assert all(good["rgb_available"].values())
        screenshot("normal-degraded-rgb")
        choose("crack/000.png", "restored_only")
        plain_png = page.locator("img[alt='Restored normalized map']").screenshot()
        candidate = choose("crack/000.png", "candidate_2", True)
        overlay_png = page.locator("img[alt='Restored normalized map']").screenshot()
        assert plain_png != overlay_png
        assert page.locator("img[alt='GT evaluation only']").count() == 1
        screenshot("candidate2-gt-rgb")
        choose("crack/000.png", "candidate_2", False)
        assert page.locator("img[alt='GT evaluation only']").count() == 0
        assert page.locator("img[alt='Restored normalized map']").screenshot() == plain_png
        missing = choose("crack/016.png", "candidate_1")
        assert not any(missing["rgb_available"].values())
        assert page.locator("#panels").inner_text().count("Unavailable:") == 2
        screenshot("candidate1-unavailable")
        for variant in ("mean_0.5_0.5", "max"):
            choose("crack/016.png", variant)
            assert page.locator(f"img[alt='{variant} normalized map']").count() == 1
        with page.expect_download() as pending:
            page.locator("a[download='summary.csv']").click()
        download = pending.value
        downloaded = args.output / f"export-{args.phase}.csv"
        download.save_as(downloaded)
        assert downloaded.read_bytes() == (ROOT / catalog["analysis"] / "summary.csv").read_bytes()
        page.set_viewport_size({"width": 760, "height": 1000})
        screenshot("narrow")
        overflow = page.evaluate("document.documentElement.scrollWidth>innerWidth")
        log = {"browser": "Microsoft Edge headless", "browser_version": browser.version,
               "playwright": importlib.metadata.version("playwright"), "phase": args.phase,
               "real_browser_rendered": True, "screenshots": images, "console_errors": errors,
               "console_warnings": console_warnings, "request_failures": failed, "http_errors": http_errors,
               "narrow_horizontal_overflow": overflow, "catalog_and_csv_exact": True,
               "sample_variant_metrics_and_panel_urls_checked": True, "gt_overlay_roundtrip": True,
               "normal_aupro_null": True, "rgb_availability_checked": True, "export_exact": True}
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        browser.close()
    print(json.dumps(log, ensure_ascii=False))
    if args.phase == "after" and (errors or failed or http_errors or overflow):
        raise AssertionError("Browser console/network/layout issue remains; inspect saved log")


if __name__ == "__main__":
    main()
