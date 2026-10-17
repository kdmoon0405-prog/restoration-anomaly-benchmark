# VisA pcb2 input subset

Dataset: Visual Anomaly (VisA), released by Amazon Science.
Creators: Yang Zou, Jongheon Jeong, Latha Pemula, Dongqing Zhang, Onkar Dabeer.
Source: https://github.com/amazon-science/spot-diff
Original archive: https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar
Official split source: https://github.com/amazon-science/spot-diff/blob/main/split_csv/1cls.csv
License: Creative Commons Attribution 4.0 International (CC BY 4.0),
https://creativecommons.org/licenses/by/4.0/
The complete original LICENSE-DATASET and publisher NOTICE accompany the bundle.

Citation: Zou et al., SPot-the-Difference Self-Supervised Pre-training for Anomaly
Detection and Segmentation, ECCV 2022. https://arxiv.org/abs/2207.14315

Packaging by the restoration-anomaly-benchmark project: only the pcb2 category
referenced in its frozen 1101-board inventory, including 100 anomalous GT masks,
and the complete unchanged official 1-class split CSV. Other categories and the
reorganized visa_pytorch duplicate tree are omitted. Images, masks and CSV bytes
are unchanged; no resize, re-encoding, mask conversion or GT-based tile selection
has been performed. The subset and ZIP packaging are the only changes. This is
input redistribution, not a model result, and does not imply author endorsement.

Dataset inputs are distributed as a separate GitHub Release asset, not committed
to Git. This explicitly licensed VisA input bundle does not change the local-only
policy for MVTec images, qualitative panels, raw research predictions or screenshots.
