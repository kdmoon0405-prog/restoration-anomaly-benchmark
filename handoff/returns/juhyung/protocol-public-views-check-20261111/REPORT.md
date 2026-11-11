# Protocol public views: GPU-side check, exporter change, and a correction (2026-11-11)

## 1. Hazelnut relative-path copies prepared by the CPU (`protocol-public-views-20261111`, `346f95e`)

Checked against the original execution files kept on the GPU host. Nothing was regenerated.

| run | local original SHA = `execution_protocol_sha256` | returned PROTOCOL.json = local original | unit receipts referencing it | public copy SHA = PROVENANCE = RECEIPT | JSON keys differing | absolute path left |
| --- | --- | --- | --- | --- | --- | --- |
| hazelnut-noise23 | yes (`fc42a68a…6c00`) | yes | 8/8 | yes (`971a4e1c…0880`) | `v1_bank_dir` only | no |
| hazelnut-noise37 | yes (`287f1b21…7779`) | yes | 8/8 | yes (`0530c2b2…917d`) | `v1_bank_dir` only | no |

- The original execution PROTOCOL files and the unit receipts are preserved unchanged on the GPU host.
- The CPU copies use LF line endings throughout. The originals use CRLF. JSON values are identical apart from `v1_bank_dir`.
- The paths pushed in `5ea2509` and `eaa60fc` remain in Git history. The public copies do not remove them.

## 2. Exporter change (`exp/image-score-aggregation-juhyung@db5a828`, `1cfe140`)

`scripts/prepare_team_return.py` was copied from `handoff/juhyung` (`d0a5c5b`) and extended. Tests: `tests/test_team_return.py` (existing, unchanged, passes) and `tests/test_team_return_public_paths.py` (new).
- **JSON string values:**
  - An absolute local path under an explicit `--local-root` is rewritten repository-relative; the root itself becomes `.`.
  - The rewrite is textual on the encoded literal, so all other bytes stay identical, including CRLF.
  - The result must parse to the original object with only those values replaced.
  - The RECEIPT entry then carries `public_path_view: true`, `original_sha256`, `original_bytes` and `changed_fields` (JSON pointers).
- **Refusals:**
  - Any other absolute path in a JSON value (drive, UNC or POSIX) is refused.
  - CSV/Markdown/text containing a drive-letter path or a `/Users|home|mnt|root/` prefix is refused.
- **Check on real files:** applied to the original Screw seed-23 PROTOCOL, it changes only `/v1_bank_dir` and records original SHA `0afcd712…b0be`.
- **First use:** the image-score aggregation returns. Their session `argv` paths became `.` and `outputs/…`.

## 3. Correction: Screw public copies (`8bebc89`, `ba4672d`)

The two Screw `PROTOCOL.public.json` files I made by hand on 2026-11-11 differ from the original in one more byte than stated.
- The rewritten `v1_bank_dir` line lost its CR: 1,827 CR vs 1,828 lines.
- JSON values are identical apart from `v1_bank_dir`, and each file matches its RECEIPT.
- The statement "all other bytes are identical" in those two RUN_RECORDs is therefore inaccurate by that line ending.
- The returned files are kept as they are. The new exporter preserves CRLF.
