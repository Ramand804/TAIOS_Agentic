# Day 3C — deterministic RiskModel

## Responsibility and API

`RiskModel().evaluate(risk_input)` returns an immutable RiskAssessment. The model is stateless and uses the immutable RiskConfig already bound to RiskInput; there is no second configuration that can disagree with it. Only the exact RiskInput type is accepted. Raw events, dictionaries, TrustAssessment and prior RiskAssessment objects are rejected. No detector, trust computation, asset lookup, operational-limit check or agent orchestration is performed.

Inspected the authoritative RISK_MODEL_SPEC.md and RISK_INPUT_IMPLEMENTATION.md, core/risk_input.py, core/risk_assessment.py, intelligence/risk_input_builder.py, config/risk.yaml, tests/test_risk_inputs.py and relevant public trust contracts. Added intelligence/risk_model.py, tests/test_risk_model.py and this document. No existing files changed.

## Equation, coverage and contributions

For AVAILABLE components A, original configured weights w and supplied component values x:

`W = sum(w_i for i in A)`

`effective_weight_i = w_i / W` for available components when W > 0

`contribution_i = effective_weight_i * x_i`

`risk_score = sum(contribution_i)`.

The implementation reuses RiskInput's generic availability, weighted coverage and effective weights. It sums contributions with math.fsum. There is no special-case two-component equation. Current defaults naturally produce W=.45 and weights TRUST=.5555555555555556, CRITICALITY=.4444444444444445, THREAT=ANOMALY=0.

Coverage remains original available weight, never the component count. Full availability yields W=1; threat plus distrust plus criticality yields .85; anomaly plus distrust plus criticality yields .60. Supplied independent future signals are supported without implementing their detectors.

RiskAssessment retains component values, availability, original/effective weights and component_contributions keyed in THREAT/TRUST/CRITICALITY/ANOMALY order. These fields jointly provide the complete decomposition. The target criticality is consumed exactly as supplied; no operation damage or source criticality is substituted.

## Missing versus known zero

With positive W, an unavailable component retains null value, zero effective weight and zero contribution. No value is imputed. A supplied available zero has positive effective weight if its original weight is positive; it contributes zero but increases the denominator, potentially lowering normalized risk. This behavior is tested for both threat and independent anomaly. It distinguishes observed absence in that signal from ignorance and does not establish overall safety.

With W=0, score, effective weights and contributions are all null. Status remains INSUFFICIENT_INPUTS. No fallback 0 or .5 is returned. The existing RiskAssessment already supports this, so no contract refinement was needed.

**Existing contract limitation:** Day-3B RiskInput requires trust and criticality values and always marks them AVAILABLE. It cannot express literally only threat observed, or all four signals missing under default weights. Single/no-usable-component mathematical tests therefore use explicit fixture weights (.4,0,0,.6) for threat/trust/criticality/anomaly. Available threat alone carries positive usable weight .4; without threat and anomaly, usable weight is zero. Trust/criticality remain observed with zero weights. These are not claims that a default-weight threat-only observation was represented. The tests verify generic arithmetic without broadening the frozen contract or changing canonical configuration. Nullable trust/criticality input support remains future contract work.

## Numeric behavior and immutability

RiskInput validates finite bounded values and explicit availability. Original weights remain unchanged. Computed risk outside [-1e-12,1+1e-12] is rejected; only final representational boundary roundoff within that tolerance is corrected to [0,1]. Contributions retain full precision and agree with risk within the assessment's existing absolute tolerance 1e-12. There is no clipping of invalid inputs.

The model copies constructor fields into the frozen assessment, preserves upstream reasons and adds deterministic component contribution/unavailability explanations. It neither parses upstream reasons nor reconstructs context. Input mappings/values remain unchanged. Optional audit may be attached afterward using the existing contract; the model creates no audit metadata. Identical inputs produce identical assessment exports with no randomness, wall-clock time or mutable model state.

Model version is `day3c-model-v1`. The existing input configuration fingerprint and version are preserved. Current diagnostic configuration fingerprint is `0efdc73c78e49c5fe8deeb01de20383e75f93e75e74f459c5af535f0698ea424`. This retains Day-3B's limitation: a full experimental identity still needs trust/reference configuration binding by a future run-level caller.

## Double counting, thresholds and interpretation

EXCLUDED_CORRELATED anomaly stays null with zero contribution. The model does not inspect TrustAssessment evidence or operational limits to reconstruct it. An explicitly supplied independent anomaly fixture is included according to its availability. Source-category declarations remain a trusted input contract, not proof that an external detector is independent.

Existing thresholds .20/.40/.55/.70/.85 are unused and unchanged. No action, qualitative risk class or authorization is produced. Weights and all component scales remain UNCALIBRATED. This conditional consequence-aware concern index is not attack probability, physical-loss prediction or a safety guarantee. Different coverage masks change the denominator; compare contributions and masks alongside score changes.

## Actual seed-42 diagnostics

Ten events per scenario with observable-state enrichment. Regenerated inputs were explicitly compared with the saved Day-3B inputs in results/day3b-inputs.json: all matched exactly. Each selected input was evaluated twice with identical outputs. Full assessments are saved in ignored results/day3c-risk.json. Scenario/event annotations below are external diagnostics, never model inputs.

Every row has coverage .45, effective distrust weight .5555555555555556 and effective criticality weight .4444444444444445. Threat/anomaly values remain null, effective weights zero and contributions zero. Values below are rounded for display only.

| Scenario/event | Trust | Distrust | Criticality | Distrust contribution | Criticality contribution | Risk |
|---|---:|---:|---:|---:|---:|---:|
| S1/6 | 0.800950781 | 0.199049219 | 0.86 | 0.110582899 | 0.382222222 | 0.492805122 |
| S2/4 | 0.801447461 | 0.198552539 | 0.91 | 0.110306966 | 0.404444444 | 0.514751411 |
| S2/5 | 0.801823096 | 0.198176904 | 0.91 | 0.110098280 | 0.404444444 | 0.514542725 |
| S2/6 | 0.798281429 | 0.201718571 | 0.91 | 0.112065873 | 0.404444444 | 0.516510317 |
| S2/7 | 0.794688645 | 0.205311355 | 0.91 | 0.114061864 | 0.404444444 | 0.518506308 |
| S2/8 | 0.791468016 | 0.208531984 | 0.91 | 0.115851102 | 0.404444444 | 0.520295547 |
| S3/6 | 0.801451697 | 0.198548303 | 0.95 | 0.110304613 | 0.422222222 | 0.532526835 |
| S5/5 | 0.801823096 | 0.198176904 | 0.91 | 0.110098280 | 0.404444444 | 0.514542725 |
| S5/6 | 0.802201697 | 0.197798303 | 0.91 | 0.109887946 | 0.404444444 | 0.514332391 |
| S5/7 | 0.802582523 | 0.197417477 | 0.91 | 0.109676376 | 0.404444444 | 0.514120821 |

S1 event 6 targets PUMP-01 (.86), giving a nonzero consequence baseline; it is not required to have zero risk. S2 targets MOTOR-02 (.91): events 5→6→7→8 show declining trust, increasing distrust and increasing risk. The change equals (.25/.45) times the distrust change within numeric tolerance. This demonstrates arithmetic responsiveness, not successful attack detection.

S3 targets PLC-03 (.95). Its .532526835 risk retains INCOMPLETE coverage and insufficient behavioral semantics. The substantial target consequence contribution must not be reported as credential-compromise detection. S5 targets MOTOR-02 (.91): risk decreases from .514542725 to .514332391 to .514120821 across events 5–7. No stale NORMAL-mode anomaly is reconstructed.

## Verification and limitations

Complete suite: **378 passed, 0 failed**, including all existing 352 tests. The 26 new cases cover hand-calculable two/three/four-component formulas; one/no usable weighted component; coverage and normalized weights; contribution sums; known-zero versus missing; bounds at 0/1 and interior values; deterministic replay; input/output immutability; strict input type rejection; S1/S2/S3/S5 properties; hidden-label/provenance/audit mutation invariance; and correlated exclusion versus independent anomaly inclusion.

Syntax checks cover both new Python files. Whitespace checks cover git diff and each new file. No existing contract or frozen-code defect was changed. Limitations remain required trust/criticality inputs, incomplete evidence, uncalibrated weights, caller-owned same-source freshness, future configuration binding and lack of predictive validation.

Trust mathematics, scenarios, Day-1 fingerprints, risk weights and action thresholds are unchanged. No RiskAgent, other agents, detectors, adaptation, authorization model, LLM or LangGraph integration was implemented. Stop after Day 3C.
