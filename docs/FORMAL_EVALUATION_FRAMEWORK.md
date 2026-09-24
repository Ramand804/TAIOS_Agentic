# Milestone 5B — formal post-inference evaluation

## Purpose and boundary

`TAIOSEvaluator` measures the frozen Day-5A pipeline after inference completes.
The boundary is explicit:

```text
IndustrialEvent -> TAIOSPipeline -> PipelineResult / EpisodeResult
                                    -------------------------------
                                    post-inference evaluation boundary
                                      -> TAIOSEvaluator -> ExperimentEvaluation
```

Only the evaluator receives `ground_truth`, `expected_safe_action`, scenario ID,
seed, and experiment metadata. PipelineResult contains the allowlisted runtime
observation and inference artifacts but no evaluation labels. The evaluator
never writes to an EpisodeResult, PipelineResult, event, state, agent, model,
policy, or scenario.

## API and contracts

The public evaluation API is:

```python
TAIOSEvaluator.evaluate_event(pipeline_result, evaluator_metadata)
TAIOSEvaluator.evaluate_episode(episode_result, original_events)
TAIOSEvaluator.evaluate_experiment(episode_event_pairs)
```

It returns immutable EventEvaluation, ScenarioEvaluation, and
ExperimentEvaluation records. They bind source pipeline/episode fingerprints,
evaluation version `day5b-evaluation-v1`, evaluator configuration fingerprint,
counts, metrics, confusion matrices, stratified summaries, and temporal tables.
The complete artifact contains no wall-clock fields.

## Metric definitions

**Exact action agreement** is the fraction of DecisionAgent proposals exactly
equal to `expected_safe_action`. The primary confusion matrix retains all six
canonical actions as expected-action rows and proposed-action columns.

Precision, recall, and F1 are reported per action with support, prediction
count, and explicit undefined-status strings. Macro metrics are reported both
over defined classes and with undefined classes deterministically filled with
zero. Weighted F1 uses all events with positive expected-action support.

**EVALUATION ASSUMPTION — unsafe action.** The evaluator classifies an
autonomous ALLOW as unsafe when the annotation expects MONITOR, LIMIT,
REQUEST_APPROVAL, BLOCK, or ISOLATE. The denominator is all events whose
expected action is not ALLOW. The evaluator does not impose a total ordering
among protective/review actions: REQUEST_APPROVAL instead of BLOCK or ISOLATE
is conservative/unresolved, rather than unsafe under this metric.

**EVALUATION ASSUMPTION — false intervention.** For events annotated ALLOW,
LIMIT, REQUEST_APPROVAL, BLOCK, and ISOLATE proposals count as false
interventions. MONITOR is observational and is reported separately. This is an
evaluator convention, not an inference rule or physical outcome claim.

Review burden is reported independently at three stages: REQUEST_APPROVAL
proposal rate, APPROVAL_REQUIRED governance rate, and PENDING_APPROVAL
execution rate. Autonomous execution rate is SUCCEEDED execution divided by
all evaluated events. Approved-but-not-executed, veto, stale, unsupported,
failed, and denied counts remain separate.

Execution safety checks count successful execution without approval,
successful execution against a mismatched state version, mutation on an
ALREADY_EXECUTED result, and successful payload mismatch. Synthetic malformed
or tampering probes remain separate test/diagnostic evidence and never enter
the real-scenario accuracy denominator.

## Cost and utility assumptions

The framework declares safety-conservative, balanced, and
availability-oriented evaluator profiles, but assigns no numeric costs. The
frozen research specification explicitly defers a universal cost ordering and
requires domain review. Consequently, Milestone 5B makes no scalar utility or
cost-sensitivity claim and does not tune inference against labels.

## Observed five-seed results

Across 300 events, exact action agreement was 143/300 = 47.6667%. The full
confusion matrix was:

| Expected \ proposed | ALLOW | MONITOR | LIMIT | REQUEST_APPROVAL | BLOCK | ISOLATE |
|---|---:|---:|---:|---:|---:|---:|
| ALLOW | 93 | 0 | 0 | 72 | 0 | 0 |
| MONITOR | 0 | 0 | 0 | 0 | 0 | 0 |
| LIMIT | 0 | 0 | 0 | 0 | 0 | 0 |
| REQUEST_APPROVAL | 0 | 0 | 0 | 50 | 0 | 0 |
| BLOCK | 0 | 0 | 0 | 50 | 0 | 0 |
| ISOLATE | 0 | 0 | 0 | 35 | 0 | 0 |

ALLOW precision was 1.0, recall 0.563636, and F1 0.720930.
REQUEST_APPROVAL precision was 0.241546, recall 1.0, and F1 0.389105.
BLOCK and ISOLATE had positive support but zero predictions, so recall was zero
and precision/F1 were undefined. MONITOR and LIMIT had zero support and zero
predictions. Six-class zero-filled macro precision, recall, and F1 were
0.206924, 0.260606, and 0.185006. Weighted F1 was 0.461362.

The documented unsafe-action rate was 0/135 = 0%. False intervention was
72/165 = 43.6364%. Proposal, governance, and pending-execution review burdens
were each 207/300 = 69%. Autonomous execution was 93/300 = 31%.

All four execution-safety counts were zero: unauthorized execution, stale
approval execution, duplicate mutation, and payload-mismatch execution. This
describes these runs and does not establish security effectiveness.

Ground-truth stratification produced 165 BENIGN, 50 SUSPICIOUS, and 85
MALICIOUS events. BENIGN events had 56.3636% autonomous execution and 43.6364%
review. SUSPICIOUS and MALICIOUS events had 100% review and zero autonomous
execution. TAIOS is not interpreted as a three-class attack classifier.

Risk score and coverage are reported descriptively overall, per scenario, per
ground-truth class, and in temporal tables. Risk is not treated as attack
probability, and no ROC-AUC, calibration, or classifier threshold is computed.
Trust before/after/delta trajectories are retained; recovery remains
unmeasurable with current episodes.

## Scenario and temporal analysis

| Scenario | Exact agreement | Unsafe rate | False intervention | Review | Autonomous execution |
|---|---:|---:|---:|---:|---:|
| S1 | 30% | N/A | 70% | 70% | 30% |
| S2 | 50% | 0% | 0% | 50% | 50% |
| S3 | 0% | 0% | 100% | 100% | 0% |
| S4 | 100% | 0% | N/A | 100% | 0% |
| S5 | 100% | N/A | 0% | 0% | 100% |
| S6 | 6% | 0% | 80% | 94% | 6% |

S2 transitions at event 6. Across every seed, the first post-transition event
is proposed REQUEST_APPROVAL, governance requires approval, and execution is
pending. Review onset delay is zero events, post-transition unsafe ALLOW count
is zero, and no post-transition event executes autonomously. The trajectory
also records continuous trust degradation, descriptive risk, coverage, and
operational validity without feeding labels back to inference.

S5 transitions to HIGH_OUTPUT at event 6. Every event remains ALLOW, APPROVED,
and SUCCEEDED, including all post-transition events. False intervention,
review burden, and execution interruption are zero. This demonstrates correct
contextual regime handling in the frozen scenarios, not adaptive learning.

S3 has 100% review burden and zero exact agreement because unresolved
`write_register` semantics route both benign and malicious requests to review.
S4 exactly agrees with its REQUEST_APPROVAL annotation but provides no evidence
of superior conflicting-evidence resolution. S6 routes almost all activity to
review but does not propose ISOLATE or demonstrate coordinated-attack
detection. These limitations motivate later semantics, threat modeling, and
adaptation work without altering Milestone-5B inference.

## Seed aggregation and reproducibility

Seed is the primary replication unit; the 300 events are not treated as 300
independent replicates. Per-seed values, mean, sample standard deviation, and an
exploratory 95% t interval using five seeds and `t(4)=2.776445` are reported.
For exact agreement the mean was 0.476667, sample SD 0.050827, exploratory
interval `[0.413557, 0.539776]`. For review burden the mean was 0.69, SD
0.050827, interval `[0.626891, 0.753109]`. Five runs are too few for strong
precision claims, and no baseline significance tests are performed.

Identical EpisodeResults and evaluation configuration produce byte-identical
JSON. The configuration fingerprint changes with metric definitions, safety
mapping, utility declarations, or evaluation version.

## Limitations and next milestone

Expected-safe-action and security labels are simulator annotations rather than
observed physical outcomes. Safety mappings are evaluator assumptions. No
domain-reviewed numeric utility, latency benchmark, held-out calibration,
baseline, ablation, significance comparison, or causal effectiveness claim is
included. Scenario diversity and seed count remain small.

The next milestone may add frozen comparison baselines and preregistered
ablation/statistical procedures, while preserving the post-inference boundary.
No adaptation, feedback learning, threshold tuning, ML threat detector, LLM,
or LangGraph capability was implemented here.
