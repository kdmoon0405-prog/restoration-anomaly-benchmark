# Experiment artifact policy

## Goal

재현성을 유지하면서 repository를 소스 코드와 해석 가능한 결과 중심으로 관리한다.

## Commit to Git

- source code and tests
- experiment protocol and decision log
- exact run commands
- split definitions / seeds
- environment metadata
- checkpoint/source SHA-256
- small CSV / JSON result tables
- analysis summaries
- selected qualitative figures needed to support a claim

## Keep outside normal Git

- MVTec/VisA images and masks
- model checkpoints
- FAISS memory banks
- raw full-run NPZ prediction dumps
- full anomaly-map image dumps
- temporary rendered/restored datasets

These artifacts are not unimportant. They are high-value reproducibility inputs/outputs, but they are binary and/or large. Store them on a shared drive, local experiment disk, artifact storage, Git LFS, or release artifact system as appropriate.

## For every external raw artifact, preserve

- logical artifact name
- experiment/run ID
- dataset/category
- code commit
- command
- file checksum
- file size
- storage location known to the team

A future run should be reproducible from committed code/config plus the recorded dataset/checkpoint sources. A future post-hoc analysis should be possible either from the archived NPZ or by regenerating it with the recorded command.
