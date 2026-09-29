# Experimental design source notes

| Topic | Frozen source | Verification |
|---|---|---|
| RQs/hypotheses and claim boundaries | `analysis/EVIDENCE_AND_CLAIMS_FREEZE.md` | Status excluded from design prose. |
| Scenarios and chronology | `environment/scenarios.py`, `docs/EXTENDED_SCENARIOS.md` | S7--S9 added after assurance freeze. |
| Configurations | `core/ablation_configuration.py`, `publication/tables/table01_configurations.json` | Seven valid configurations; governance exclusion. |
| Matrix/seeds/events | frozen publication artifact | 20 seeds, 1,260 episodes, 4,200 unique scenario/seed events. |
| Metrics | `evaluation/formal_evaluator.py`, publication artifact | Evaluator-only expected actions; denominators retained. |
| Aggregation/statistics | `evaluation/statistical_analysis.py` | Seed is replication unit; constant-difference handling. |
| Leakage/reproducibility | `core/runtime_inputs.py`, leakage tests, frozen hashes | Allowlisted runtime projection. |
