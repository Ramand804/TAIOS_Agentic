# Day 3B — label-safe risk inputs and assessment primitives

## Purpose and scope

Implemented immutable input/configuration/output contracts and a deterministic adapter. No RiskModel, RiskAgent, detector, decision policy or final risk computation is provided. Frozen Day-1 and trust files, risk weights and thresholds are unchanged. All parameters remain UNCALIBRATED.

Read `RISK_MODEL_SPEC.md` first. Inspected `config/risk.yaml`; trust agent, assessment, evidence and state; event, assets, industrial state and operational limits; runtime projection, asset validator, EventManager and Orchestrator; trust evaluation harness/metrics and existing tests. Reviewed directory conventions under core/intelligence/agents/tests. No models directory was created.

Added `core/risk_input.py`, `core/risk_assessment.py`, `intelligence/risk_input_builder.py`, `tests/test_risk_inputs.py` and this document. No existing tracked files were modified.

## RiskInput and configuration

`RiskInput` is a frozen, keyword-only dataclass containing source_id, target_id, operation, composite_trust, distrust_score, criticality_score, trust_state_version, trust_evidence_coverage, prior_only_dimensions, config, threat_probability, threat_available, threat_score_kind, anomaly_score, anomaly_available, anomaly_category and reasons. The source entity namespace is derived as `asset:<source_id>`.

No audit IDs, experimental sequence/timestamp, labels, provenance or final risk_score belong to this input. Mappings are copied into read-only mapping proxies; coverage signs and reasons are tuples. `to_dict()` emits independent JSON-compatible copies with computed availability, coverage details, weights, configuration fingerprint/version and calibration status.

All supplied scores must be finite numeric values in [0,1]; booleans are rejected. Distrust must equal the complement of supplied composite within absolute tolerance 1e-12. Version must be a nonnegative integer. Five trust coverage dimensions and their permitted ordered sign lists are validated. Availability is a strict boolean and must agree exactly with non-null value presence. Available zero-valued signals are supported by the contract and are distinct from unknown. Available threat additionally declares CONFIDENCE or CALIBRATED_PROBABILITY; this is source metadata, not calibration performed by this code.

`RiskConfig.load(path=None)` reads canonical config/risk.yaml relative to the module, independent of working directory. It maps threat/distrust/criticality/anomaly to THREAT/TRUST/CRITICALITY/ANOMALY. Original weights are validated, never silently normalized: nonnegative, finite, sum one within absolute tolerance 1e-9. Existing .40/.25/.20/.15 are not duplicated as code defaults. Thresholds .20/.40/.55/.70/.85 remain in YAML and are not activated or used as classifications.

The SHA256 fingerprint covers these risk weights, input contract version `day3b-input-v1`, missing/dependency policies and UNCALIBRATED status. It is a **risk-input configuration identity**, not a complete future experimental identity: TrustAssessment has no public trust-configuration fingerprint, and this adapter neither invents nor reads private model configuration. A later run-level assessment identity must also bind approved trust/reference configurations as required by Day 3A. Thresholds do not affect input preparation and are excluded from this fingerprint.

## Builder and trust integration

```python
risk_input = build_risk_input(
    runtime_observation(event),
    trust_assessment,
    config=RiskConfig.load(),  # optional; loaded when omitted
)
```

The adapter accepts only the exact runtime projection dictionary plus a public TrustAssessment. It checks allowlisted fields/context enums, uses `to_inference_dict()` to remove audit, verifies the source entity, and copies post-observation composite, version, direct coverage and cumulative prior-only dimensions. It computes only `distrust_score = 1 - composite_trust`; it does not run, update or recalculate trust.

Prior-supported trust remains available with its explicit evidence limitations. Insufficient behavior/context does not become low trust or negative evidence. Direct HISTORY may remain insufficient while internal historical trust has evolved. The caller must pair the current observation and assessment within the same transaction. A source mismatch is rejected; a stale assessment for the same source cannot be identified from this API alone. Audit IDs are deliberately not used to infer freshness or parse scenario identity.

## Target criticality and integrity

The adapter reuses `validate_event_asset_integrity` through a SimpleNamespace containing only safe projection fields and a fixed `risk-input` error label. This preserves the Day-1 source/type/zone/protocol and target/type/criticality checks without constructing an IndustrialEvent with fake labels or weakening EventManager. Unknown assets and metadata disagreement raise the existing EventIntegrityError. The fixed error label has no experimental information.

Criticality is the registered **target** value: MOTOR-02 .91, PLC-03 .95, PUMP-01 .86. Source criticality is never substituted. No action damage multiplier or operation authorization score exists. Direct low-level contract fixtures validate numeric bounds; registry consistency is enforced by the builder at the observation boundary.

## Threat and anomaly availability

The builder always emits threat_probability=null, threat_available=false, threat_score_kind=UNAVAILABLE. No threat detector exists. Known-zero threat is possible only in an explicitly supplied contract fixture or a separately reviewed future signal source; absence of a detector does not establish zero threat.

The builder always emits anomaly_score=null and anomaly_available=false. It neither recomputes nor fuses a limit-deviation candidate. For the current frozen extractor profile, supported BEHAVIOR coverage records the category OPERATIONAL_LIMIT_SHARED_WITH_TRUST and status EXCLUDED_CORRELATED. Insufficient behavior records category NONE and status MISSING with NO_INDEPENDENT_ANOMALY. This metadata describes the current source category, not a general detector provenance framework.

Both statuses exclude anomaly from fusion. Positive/negative behavioral sign or magnitude never enables it. The contract rejects available anomaly with the shared category; only an explicit INDEPENDENT category may accompany an available value. No builder argument enables a detector or ablation. Future independent detector integration requires separate review; declaring a category is not proof of independence against a malicious caller.

**Day-3A refinement required by the Day-3B request:** the specification allowed retaining a computed operational candidate outside fusion. This task explicitly requires anomaly_score=null and implements no detector. Therefore no candidate is materialized or counted as observed. Observation-weight coverage is .45 here, rather than the conditional .60 example in Day 3A that assumed a retained candidate. The exclusion rule and fusion-weight coverage .45 are unchanged. No specification or frozen code was silently edited.

## Coverage and effective weights

Availability is explicit, never based on numeric truthiness. TRUST and CRITICALITY are required by this current adapter/contract. THREAT is MISSING. ANOMALY is MISSING or EXCLUDED_CORRELATED. Metadata reports ordered included/observed/missing/excluded components, original-weight coverage, observation-weight coverage and an incomplete status.

Coverage is the sum of original weights of AVAILABLE components: .25+.20=.45. This is weighted coverage, not 2/4 and not probabilistic confidence. Current effective weights are:

| Component | Original | Effective |
|---|---:|---:|
| THREAT | .40 | 0 |
| TRUST (distrust input) | .25 | .5555555555555556 |
| CRITICALITY | .20 | .4444444444444445 |
| ANOMALY | .15 | 0 |

Zero effective weight is accounting exclusion, not an imputed zero signal. If all original weight mass is on unavailable components, coverage is zero and effective weights are all null. Status is INSUFFICIENT_INPUTS. Otherwise missing/excluded positive-weight components or insufficient trust evidence cause INCOMPLETE; COMPONENTS_PRESENT does not claim calibrated confidence.

## RiskAssessment contract

`RiskAssessment` is a frozen subclass retaining all RiskInput fields and properties, adding risk_score, component_contributions, model_version and optional separated AuditCorrelation. Original/effective weights, coverage, availability, trust version and risk configuration identity are inherited. `to_inference_dict()` excludes audit; `to_dict()` adds it afterward.

There is no assessment-producing factory or scoring API. A future model must supply the score and contributions. Constructor validation checks their bounds, agreement with supplied inputs/effective weights and additive consistency; it rejects contradictory records rather than computing a result for the caller. With weighted inputs present a null score is rejected, so a RiskInput is the unevaluated type. When coverage is zero, the only valid assessment has null score and null contributions. This is not a partially evaluated placeholder.

Tests use hand-specified zero-valued and no-weighted-input contract fixtures only. The scenario diagnostics never instantiate RiskAssessment or calculate a final risk.

## Leakage boundary and determinism

Raw IndustrialEvent, full event dictionaries, evaluation-enriched rows and additional context fields are rejected. The builder has no access to ground truth, scenario, provenance, synthetic scores or audit IDs. It does not parse TrustAssessment reasons into risk signals. Source/target IDs serve attribution/reference checks only.

Tests mutate ground_truth, expected_safe_action, scenario_id, provenance phase/transition/causal tags, experimental IDs/time/sequence and synthetic anomaly/threat/prior-trust/compromise context. Fresh trust inference and risk inputs remain identical for S1/S2/S3/S5. Differing assessment audit IDs do not change input exports. Identical safe observations, assessments and risk configurations produce identical normalized outputs, with no random or wall-clock dependency.

## Observed seed-42 diagnostics

Actually executed using ten events per scenario, observable-state enrichment, fresh TrustAgent per run, source-local observation counters and existing EventManager validation. Repeated the complete diagnostic construction twice: serialized output was byte-identical. Full inputs are saved in ignored `results/day3b-inputs.json`. Scenario/event columns below are diagnostic annotations added outside inference.

Every row has threat=null/false, anomaly=null/false, weighted coverage=.45 and the effective weights listed above. No final risk score was calculated. Values below are display-rounded; JSON retains full precision.

| Scenario/event | Source | Target | Composite trust | Distrust | Target criticality |
|---|---|---|---:|---:|---:|
| S1/6 | SERVICE-03 | PUMP-01 | 0.800950781250 | 0.199049218750 | 0.86 |
| S2/4 | PLC-07 | MOTOR-02 | 0.801447460937 | 0.198552539063 | 0.91 |
| S2/5 | PLC-07 | MOTOR-02 | 0.801823095703 | 0.198176904297 | 0.91 |
| S2/6 | PLC-07 | MOTOR-02 | 0.798281429036 | 0.201718570964 | 0.91 |
| S2/7 | PLC-07 | MOTOR-02 | 0.794688645426 | 0.205311354574 | 0.91 |
| S2/8 | PLC-07 | MOTOR-02 | 0.791468016052 | 0.208531983948 | 0.91 |
| S3/6 | HMI-02 | PLC-03 | 0.801451696777 | 0.198548303223 | 0.95 |
| S5/5 | PLC-01 | MOTOR-02 | 0.801823095703 | 0.198176904297 | 0.91 |
| S5/6 | PLC-01 | MOTOR-02 | 0.802201696777 | 0.197798303223 | 0.91 |
| S5/7 | PLC-01 | MOTOR-02 | 0.802582522583 | 0.197417477417 | 0.91 |

S1 event 6 targets PUMP-01: criticality .86 and insufficient speed semantics. S2 distrust increases from event 6 onward as operational violations reduce trust; anomaly remains excluded, avoiding duplicate fusion. S3 retains available trust and .95 target criticality with insufficient behavior/context, missing threat and missing independent anomaly. S5 distrust decreases slightly across the observed HIGH_OUTPUT transition while behavioral support remains positive; no stale NORMAL-limit anomaly is created.

## Verification and limitations

Executed the complete suite: **352 tests passed, 0 failed**, including all prior 278 tests and 74 new parameterized cases. New coverage includes nested immutability/export copies, finite bounds, availability contradictions, known zero versus missing, original/effective weights, zero available weight mass, identity stability, source mismatch, shared registry validation, correlated anomaly rejection, S1/S2/S3/S5 behavior, hidden-label/audit invariance and future assessment validation. Syntax checks passed for all four new Python files. Whitespace checks include the new untracked files as well as `git diff --check`.

No frozen-code bugs were changed. Same-source freshness remains caller-owned; independent signal categories are contracts, not authenticated provenance. Missing trust/criticality adapters, full risk-run identity, reference-version binding, missing operation semantics, detector integration, risk arithmetic, calibration and policy thresholds remain future work. Direct contract construction is for trusted callers; schema validation is not a sandbox against malicious Python code. Current confidence is explicitly incomplete, not a calibrated probability.

No existing public interface, configuration, scenario, Day-1 event fingerprint, trust equation or TrustAgent behavior changed. No RiskModel/RiskAgent/other agent, adaptation, authorization model, LLM or LangGraph was implemented. Stop after Day 3B.
