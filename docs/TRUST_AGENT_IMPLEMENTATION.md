# Day 2D — TrustAgent

## Responsibility and architecture

TrustAgent orchestrates the existing safe extractor and TrustModel. It does not implement another algorithm or infer an attack classification. BaseAgent was inspected and remains an unchanged placeholder: TrustAgent subclasses it without adding a generic framework. No other agents, model tuning, authorization policy, adaptation or LLM integration were added.

Inspected the four authoritative trust/coverage documents, BaseAgent, TrustModel, state/evidence contracts, safe projection, extractor, generation profile and configurations. Added agents/trust_agent.py, core/trust_assessment.py, tests/test_trust_agent.py and this document. No existing files were modified.

## API and lifecycle

```python
agent = TrustAgent()  # optional validated model_config/evidence_config
assessment = agent.assess(
    runtime_observation(event),
    delivery_token=opaque_delivery_token,
    observation_number=entity_local_ordinal,
    correlation_metadata=AuditCorrelation(event.event_id, event.sequence_number),
)
# Future downstream inference receives this view, not audit-bearing export:
result = assessment.to_inference_dict()
agent.reset()  # new isolated run with the same configurations
```

Only the existing exact label-safe dictionary is accepted. Correlation is optional and must be the immutable AuditCorrelation type; invalid metadata is rejected before inference. The agent invokes extractor, uses its `asset:<source_id>` attribution, initializes/retrieves state, and invokes the unchanged model with uncorrelated evidence. Original audit IDs are never passed to extraction/model, parsed or used as ordering tokens. The caller supplies opaque delivery identifiers and per-entity ordinals.

Identity evidence describes the identity presenting commands from this source; it does not swap an independent identity profile into a device profile. Different sources have isolated state. A new instance or reset is required at experiment boundaries; no experiment ID is inspected to guess the boundary. The model rejects duplicate tokens, ordinal reuse, gaps and out-of-order observations. Initialization is idempotent. Invalid updates do not advance scores or delivery counters; a newly seen entity may have its prior initialized before a rejected delivery. No mutable model state is publicly returned. Reset reconstructs both model and extractor from the retained validated configurations and current reference registries; repeatability assumes those reference definitions remain fixed.

## TrustAssessment contract

The frozen validated assessment extends EntityTrustState, retaining entity ID, five dimension scores, composite, observation count, local ordinal, version, history statistic, negative-history flags and cumulative evidence coverage counts. Added fields include previous composite, trust delta, previous behavioral trust, immutable evidence tuple, human-readable reasons and optional audit correlation.

Derived output properties include evidence_count, positive_evidence_count, negative_evidence_count, neutral_evidence_count, trust_state_version, behavioral_trust_delta and evidence_coverage. Counts describe direct extractor records, not internal historical evidence synthesized by TrustModel. Per-dimension coverage is an ordered list of POSITIVE/NEGATIVE effective evidence signs, or INSUFFICIENT if only neutral/zero-magnitude/missing evidence exists. This is an evidence-availability indicator, not a calibrated confidence probability. A direction count can include a zero-confidence record while effective coverage remains insufficient; this distinction is intentional.

Direct HISTORY coverage remains insufficient because Day 2B returns NO_HISTORY. The model's internal lagged historical update can still change historical trust. An additional deterministic reason explicitly identifies that change; it does not falsely count internal history as new direct observation. Neither missing evidence nor a retained .80 prior is described as proof of trustworthiness.

Validation rejects out-of-range trust, inconsistent/nonfinite deltas, mixed/correlated evidence and malformed reasons/audit metadata. Returned lists/dictionaries are copies. to_dict includes audit metadata for traceability; to_inference_dict removes audit metadata. Original event IDs can embed scenario names, so future Risk consumers must use the inference view. All evidence audit fields remain None. No qualitative TRUSTED/SUSPICIOUS/MALICIOUS categories or arbitrary thresholds are added.

## Reasons and leakage boundary

Reasons preserve extractor rule text, prefixed only with the observable operation. For example, set_speed value 97 in NORMAL is outside inclusive range [20,80]. No phase/compromise label is used. Coverage does not make a hidden recommendation or claim authorization. The historical summary describes a change attributable to retained prior observations without implementing a full explainability subsystem.

Tests alter only ground truth, expected action, provenance, scenario metadata, synthetic scores and audit IDs: all inference views remain identical. Raw events and raw event dictionaries are rejected by the existing extractor. Audit records differ only in their isolated export fields. This is a tested API boundary, not a sandbox against malicious Python callers. Delivery tokens must be preserved across retries; new tokens cannot identify disguised duplicate deliveries from identical content alone.

## Observed diagnostics

Seed 42, ten events, observable-state enrichment, fresh agent for each run. Scenario/event names are evaluation-harness annotations and are not agent inputs. P=positive effective evidence, N=negative, ?=insufficient; coverage order is identity/device/behavior/history/context. Counts refer to direct evidence. Numbers are rounded to nine decimal places.
| Scenario/event | Operation/value | Mode | Coverage I/D/B/H/C | Negative count | TB | Composite | Delta | Primary reason |
|---|---|---|---|---:|---:|---:|---:|---|
| S2/4 | set_speed 63 | NORMAL | P/P/P/?/? | 0 | 0.802000000 | 0.801447461 | +0.000371680 | set_speed: WITHIN_LIMIT: Value 63 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S2/5 | set_speed 48 | NORMAL | P/P/P/?/? | 0 | 0.802500000 | 0.801823096 | +0.000375635 | set_speed: WITHIN_LIMIT: Value 48 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S2/6 | set_speed 97 | NORMAL | P/P/N/?/? | 1 | 0.788333333 | 0.798281429 | -0.003541667 | set_speed: OUTSIDE_LIMIT: Value 97 in NORMAL; inclusive limit [20, 80], deviation 0.283333333333. |
| S2/7 | set_speed 97 | NORMAL | P/P/N/?/? | 1 | 0.774166667 | 0.794688645 | -0.003592784 | set_speed: OUTSIDE_LIMIT: Value 97 in NORMAL; inclusive limit [20, 80], deviation 0.283333333333. |
| S2/8 | set_speed 94 | NORMAL | P/P/N/?/? | 1 | 0.762500000 | 0.791468016 | -0.003220629 | set_speed: OUTSIDE_LIMIT: Value 94 in NORMAL; inclusive limit [20, 80], deviation 0.233333333333. |
| S3/4 | write_register 55 | NORMAL | P/P/?/?/? | 0 | 0.800000000 | 0.800947461 | +0.000246680 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/5 | write_register 55 | NORMAL | P/P/?/?/? | 0 | 0.800000000 | 0.801198096 | +0.000250635 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/6 | write_register 999 | NORMAL | P/P/?/?/? | 0 | 0.800000000 | 0.801451697 | +0.000253601 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/7 | write_register 999 | NORMAL | P/P/?/?/? | 0 | 0.800000000 | 0.801707523 | +0.000255826 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/8 | write_register 999 | NORMAL | P/P/?/?/? | 0 | 0.800000000 | 0.801965017 | +0.000257494 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S5/4 | set_speed 68 | NORMAL | P/P/P/?/? | 0 | 0.802000000 | 0.801447461 | +0.000371680 | set_speed: WITHIN_LIMIT: Value 68 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S5/5 | set_speed 53 | NORMAL | P/P/P/?/? | 0 | 0.802500000 | 0.801823096 | +0.000375635 | set_speed: WITHIN_LIMIT: Value 53 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S5/6 | set_speed 85 | HIGH_OUTPUT | P/P/P/?/? | 0 | 0.803000000 | 0.802201697 | +0.000378601 | set_speed: WITHIN_LIMIT: Value 85 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |
| S5/7 | set_speed 85 | HIGH_OUTPUT | P/P/P/?/? | 0 | 0.803500000 | 0.802582523 | +0.000380826 | set_speed: WITHIN_LIMIT: Value 85 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |
| S5/8 | set_speed 84 | HIGH_OUTPUT | P/P/P/?/? | 0 | 0.804000000 | 0.802965017 | +0.000382494 | set_speed: WITHIN_LIMIT: Value 84 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |

S2's event-6 behavioral and composite decreases derive from requested speed 97 exceeding the NORMAL maximum 80. Events 7/8 also have lagged negative historical contributions derived from earlier limit violations; positive identity/device support cannot cancel these losses under the existing negative-precedence rule. No compromise status is inferred or reported.

S3 has no approved register range or authorization policy. Authentication and reference consistency contribute positive evidence, but behavioral/context coverage remains insufficient. Composite rises slightly on the evidence that is available; that is not an assertion that the register write is permitted or benign. No S3 rule was introduced.

S5 current mode moves to HIGH_OUTPUT and values 85/84 use 60–95. Behavioral evidence remains positive; stale NORMAL limits are not used. The agent has no branch for the observable-state profile or a scenario name.

## Verification and limitations

264 tests passed, 0 failed, including all prior 251 tests unchanged. New tests cover assessment validation, model agreement, delta/counts, copy safety, replay/reset, entity isolation, ordering errors, audit-ID invariance, hidden-label invariance, S2 observable reasons, S3 insufficient coverage and S5 current-mode limits. Python syntax checks and git diff --check passed. No frozen-code bug was modified; this is a new orchestration/output layer only.

Trust mathematics and all parameters are unchanged. No model-state persistence, automatic experiment detection, concurrent-agent safety, calibration, qualitative classifications or downstream agents were added. Parameters remain uncalibrated and results are diagnostic, not experimental validation. Optional correlation exports are for audit only. No automatic hook was added to main.py or core/orchestrator.py, preserving frozen generation/logging behavior. Stop after Day 2D.
