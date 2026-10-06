# Industrial Testbed Acceptance Matrix

The following software-testbed acceptance cases are exercised by the industrial test suite. They are application-level simulator evidence only.

| ID | Acceptance condition | Evidence |
|---|---|---|
| IA-01 | Default simulation cannot mutate process state | `test_default_simulation_remains_non_executable` |
| IA-02 | Shadow mode cannot mutate process state | `test_shadow_mode_cannot_create_mutating_capability` |
| IA-03 | Supervised execution requires review | `test_supervised_requires_authoritative_bound_review_then_can_execute` |
| IA-04 | Controlled execution follows governance and capability path | `test_controlled_execution_uses_authoritative_governance_and_one_shot_capability` |
| IA-05 | Manual governance DTO has no authority | `test_forged_governance_and_value_identical_dto_have_no_authority` |
| IA-06 | Manual review DTO has no authority | `test_supervised_requires_authoritative_bound_review_then_can_execute` |
| IA-07 | Stores expose no registration method | `test_stores_expose_no_registration_or_capability_minting_api` |
| IA-08 | Mode race before execution fails closed | `test_mode_race_consumes_capability_without_mutation` |
| IA-09 | State race before issuance fails closed | `test_state_races_and_expiry_prevent_mutation` |
| IA-10 | State race after issuance fails closed | `test_state_races_and_expiry_prevent_mutation` |
| IA-11 | Governance/review expiry fails closed | `test_state_races_and_expiry_prevent_mutation`, `test_review_binding_and_expiry_are_enforced` |
| IA-12 | Random and incorrect tokens fail closed | `test_forged_random_wrong_and_revoked_capabilities_fail_closed` |
| IA-13 | Revocation prevents mutation | `test_forged_random_wrong_and_revoked_capabilities_fail_closed` |
| IA-14 | Sequential replay cannot mutate twice | `test_controlled_execution_uses_authoritative_governance_and_one_shot_capability` |
| IA-15 | Concurrent replay permits at most one mutation | `test_concurrent_replay_allows_at_most_one_process_mutation` |
| IA-16 | Independent interlock enforces command constraints | `tests/industrial/test_process_simulator.py` |
| IA-17 | MQTT failure modes are typed and non-executing | `tests/industrial/test_operations.py` |
| IA-18 | Audit-chain tampering is detected | `test_audit_chain_detects_tampering_and_persistence_is_append_oriented` |
| IA-19 | Read model has no execution or issuance API | `test_read_model_is_read_only_and_reports_runtime_state` |
| IA-20 | Runtime event cannot change trusted operating mode | `test_lifecycle_creates_authoritative_record_and_event_cannot_change_mode` |

All evidence must be rerun for a release candidate. It does not certify a physical plant, broker deployment, or hardware safety system.
