# Milestone 6A — operational semantic model

## Responsibility and scientific boundary

The operational semantic layer describes whether an observable industrial
request has declared, sufficiently specified, and currently valid semantics.
It does not classify attacks, select actions, grant authorization, adjust
trust/risk, or use evaluation labels.

The model consumes only the allowlisted runtime observation: source and target
identity/type, operation, requested value, protocol/zone metadata, current
production state and operating mode. Scenario ID, provenance, transition tags,
ground truth, expected action, synthetic scores, and formal evaluation results
never enter the model.

Pipeline placement is:

```text
runtime_observation
  -> OperationalSemanticModel
  -> immutable OperationalSemanticAssessment
  -> DecisionContext
```

Planning does not call the model. The assessment is propagated as an explicit
fact. Existing operational validity still feeds authority through the frozen
CapabilityEnvelope, so no authority, planning, decision, governance, or
execution policy was changed.

## Registry, API, and contract

`OperationalSemanticModel.assess(observation)` uses the versioned declarative
registry in `config/operational_semantics.yaml`. The version is
`milestone6a-operational-semantics-v1`. The registry references the canonical
`OperationalLimits` source for `set_speed`; it does not duplicate numeric
ranges.

`OperationalSemanticAssessment` records source/target scope, operation,
semantic status, value-semantics status, operational validity, known
constraints, observed value, applicable rule IDs, unresolved requirements,
reasons, policy version, and configuration fingerprint. It is immutable and
has a deterministic content fingerprint.

Statuses are:

* `SUPPORTED_VALID`: declared semantics and required context establish a valid request.
* `SUPPORTED_INVALID`: declared semantics establish that the request violates a known constraint.
* `UNDERSPECIFIED`: the operation is recognized, but required observable context is absent.
* `UNSUPPORTED`: no declared operation/target rule or canonical target/mode constraint exists.

Authorization remains distinct: it asks whether an identity/source may request
an operation. Semantic validity asks whether the requested operation/value is
meaningful under declared industrial semantics. Authorization does not imply
semantic validity.

## Supported and unresolved operations

| Operation | Target type | Current support | Required observable facts | Limitation |
|---|---|---|---|---|
| `set_speed` | actuator | Mode-aware validity when a canonical target/mode limit exists | target, operation, numeric value, operating mode | Some actuator targets, including PUMP-01, have no canonical `set_speed` limit |
| `write_register` | PLC | Recognized operation, value validity underspecified | target, value, register address, register data type/domain | Current event/runtime schema contains no register address or register-specific constraints |

For MOTOR-02, NORMAL delegates to `[20,80]` and HIGH_OUTPUT delegates to
`[60,95]`. Values outside those inclusive ranges are `SUPPORTED_INVALID`.

Inspection of every S3 event across multiple seeds confirmed that the schema
contains only target PLC, operation `write_register`, and the requested value.
It does not identify which register is written. Therefore `999` is not labeled
invalid. Every such request is `UNDERSPECIFIED`, with explicit requirements for
an observable register address and register-specific type/range declaration.

## Integration and non-coupling

TAIOSPipeline assesses semantics immediately after runtime projection and
environmental regime synchronization. The same immutable assessment is carried
by PipelineResult and both the base and authority-aware DecisionContext.
DecisionContext validates assessment scope, observed value, and agreement with
canonical WITHIN_LIMIT/OUTSIDE_LIMIT facts.

Trust evidence remains unchanged; semantic invalidity is not converted into a
trust penalty. Risk inputs and weights remain unchanged; no semantic-risk
component was added. Authorization, authority rules, candidate generation,
proposal selection, governance, and execution were not retuned.

## Coverage and structural replay

Across S1–S6, seeds 42/123/456/789/2026, and 300 events:

| Semantic status | Count | Rate |
|---|---:|---:|
| SUPPORTED_VALID | 108 | 36.00% |
| SUPPORTED_INVALID | 75 | 25.00% |
| UNDERSPECIFIED | 85 | 28.33% |
| UNSUPPORTED | 32 | 10.67% |

Fully established semantics, including both valid and invalid determinations,
covered 183/300 = 61%. All 85 `write_register` events were underspecified. The
32 unsupported requests were `set_speed` requests against actuator targets
without a canonical target/mode limit. This is semantic coverage, not accuracy.

Before and after integration, the structural distribution remained exactly:

* proposals: 93 ALLOW, 207 REQUEST_APPROVAL;
* governance: 93 APPROVED, 207 APPROVAL_REQUIRED;
* execution: 93 SUCCEEDED, 207 PENDING_APPROVAL.

The post-freeze Milestone-5B evaluator was then run unchanged. Exact agreement
remained 47.6667%, evaluator-defined unsafe-action rate 0%, false-intervention
rate 43.6364%, review burden 69%, and autonomous execution 31%. Semantic design
was completed before this descriptive label-based comparison.

## Scenario behavior

S2 retains 25 valid pre-transition requests and 25 known outside-limit
requests across five seeds. Post-transition requests remain
`SUPPORTED_INVALID`, REQUEST_APPROVAL, APPROVAL_REQUIRED, and PENDING_APPROVAL.

S3 contributes 50 `UNDERSPECIFIED` events. Its behavior remains 100% review;
the new fact is the auditable reason that register-level observable context is
missing. No register semantics were fabricated to improve evaluation results.

S5 contributes 50 `SUPPORTED_VALID` events. NORMAL and HIGH_OUTPUT constraints
come from current-mode canonical limits. All post-transition values remain
valid and execute successfully, with no stale NORMAL interpretation.

S1 and the benign portion of S6 expose a separate limitation: `set_speed` is a
recognized operation, but requests targeting actuators without a canonical
limit remain unsupported rather than receiving a fabricated range.

## Leakage, determinism, and limitations

Tests alter ground truth, expected action, scenario ID, event/audit IDs,
sequence, provenance, transition/causal fields, synthetic scores, and a formal
evaluation-like field. The complete semantic assessment remains identical.
Equal observable requests and registries produce equal assessments and
fingerprints without randomness or timestamps.

The registry covers only operations observed in the current scenarios. It has
no register catalog, address/value types, PLC program schema, unit conversion,
cross-operation constraints, rate limits, temporal command semantics, or
device capability discovery. Missing semantics remain explicit rather than
being inferred from suspicious values.

Milestone 6B can consume established validity, invalidity, underspecification,
rule IDs, known ranges, and unresolved requirements as observable semantic
facts for a separately specified threat/risk layer. No threat model, semantic
risk weight, adaptation, baseline, ML, LLM, or LangGraph feature was added in
Milestone 6A.
