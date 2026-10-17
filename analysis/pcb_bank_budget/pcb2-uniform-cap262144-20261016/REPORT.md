# Bounded PCB bank CPU draft

Index-only plan: 262,144 / 27,132,672 normal-fit patch IDs, seed 11. No actual PCB features. New uniform sampled bank, not IdentitySampler or greedy coreset.

Synthetic lazy stream: 1,000,003 rows, D=8, K=257; selected values match formula exactly. Synthetic bank COMPLETE is NOT a PCB bank. Actual PCB bank/calibration NOT_CREATED; pilot NOT_READY_FOR_PILOT.

Planned payloads: bank 1 GiB, int64 indices 2 MiB, input chunk <=32 MiB, gather <=32 MiB, finite check <=8 MiB. Python sample/sort overhead O(K) excluded. These are payload bounds, not measured RSS/VRAM. Index/scorer copies and native evaluation remain separate unresolved budgets.

Selection is uniform over the overlapping-tile patch pool, NOT over physical pixels; rare normal modes may be missed. Geometry/split/old metrics and existing runners are unchanged. See protocol and resource_plan.json.
