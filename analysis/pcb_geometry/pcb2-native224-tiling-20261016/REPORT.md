# Native PCB tiling geometry

{
  "geometry_status": "GEOMETRY_IDENTITY_PASS",
  "pilot_status": "NOT_READY_FOR_PILOT",
  "input_images": 1101,
  "official_anomaly_masks": 100,
  "implicit_normal_masks": 1001,
  "errors": [],
  "all_covered": true,
  "rgb_exact_images": 1101,
  "gt_exact_images": 1101,
  "source_components_8connected": 324,
  "lost_components": 0,
  "historical_lost_components": 19,
  "historical_lost_ids_recovered_exactly": 19,
  "tile_counts": {
    "fit": 34608,
    "calibration": 8640,
    "test": 9600
  },
  "no_scientific_metric_or_model_execution": true,
  "bank_created": false,
  "calibration_created": false,
  "teammate_prior_use": "unconfirmed"
}

Index vectors only: 103.503 GiB. Potential three simultaneous vector payloads during unchanged fit: 310.509 GiB. Arithmetic payload estimates, NOT measured RSS/runtime/VRAM; see resource_estimate.json.

No resize/pad/GT selection; original 8-connected IDs are reconstructed exactly, not physical-defect counts. Geometry pass does not establish detector or RGB quality after x4. Tile boundaries limit context. Raw RGB/GT identity reassembly is NOT an anomaly-map merger. Map overlap, board score, calibration domain, tile-wise x4, resource feasibility, runner and device/checkpoint smoke remain unfrozen. This is a separate family from center-crop/full-frame224. Negative gating/full110 B/B-uncertain are unchanged. Figures contain local-only RGB. No pilot/model/metric execution was performed.
