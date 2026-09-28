# Milestone 8C extended scenarios

S1--S6 cannot isolate decision-causal assurance because their adverse requests are already invalid or unresolved upstream.  S7--S9 are frozen evaluation scenarios with 50 events by default and phase annotations held only in provenance and evaluator metadata. `runtime_observation` exposes neither scenario ID, phase, ground truth, expected action, nor attack timing.

S7 uses PLC-07 to request valid MOTOR-02 speeds: a baseline of 35--45, followed by repeated 72--78 commands in the same NORMAL mode. Authentication, permission, and limits remain valid. The evaluator independently annotates the later phase as `REQUEST_APPROVAL`; frozen drift can identify the persistent unexplained numeric shift, while the frozen threat and trust models have no direct valid-compromise detector.

S8 is the negative control: PLC-01 shifts from 35--45 NORMAL commands to 72--88 only after an observable `HIGH_OUTPUT` mode change. The annotation is `ALLOW` throughout. S9 has baseline, valid unexplained 72--78 behavior, then valid 35--45 recovery; it observes frozen recovery behavior without adding a recovery rule.

Each seed generates one deterministic event stream that is reused across RULE_BASED, TAIOS_STATIC, TAIOS_ADAPTIVE, TAIOS_NO_TRUST, and S7 assurance OFF/ON comparisons. Scenario fingerprints are hashes of evaluator metadata. Expected-action annotations are authored from the scenario contract before comparison and are joined only by the evaluator.
