# 3. TAIOS Methodology

## 3.1 Design objectives and system model

TAIOS is a deterministic research prototype for industrial decision flows in which a command can be authenticated, authorized, and within an operational envelope while its observable behavior changes over time. Its design separates assessment from execution, uses observable evidence, escalates to least-permissive review when authority is restricted, and records traceable decision artifacts. It is not presented as a deployed industrial control system.

## 3.2 Industrial event representation

An industrial event contains source and target identifiers/types, identity, operation, requested value, network zone, protocol, authentication status, and target criticality. The runtime projection allowlists those fields plus production state and operating mode. Ground truth, expected safe action, scenario identifier, provenance phase, compromise annotations, and evaluator outputs are excluded from inference.

## 3.3 Architecture

Figure 1 shows the implemented order: event handling and observable context; operational semantics and authorization; threat, correlation, trust and risk assessment; drift; authority; assurance; planning; decision; governance; execution; outcome, memory, and feedback. Components have distinct responsibilities; no LLM, learned policy, reinforcement learning, or LangGraph component is used.

## 3.4 Context, semantics, and authorization

Operational semantics classifies requests as `SUPPORTED_VALID`, `SUPPORTED_INVALID`, `UNDERSPECIFIED`, or `UNSUPPORTED`. Authentication establishes neither permission nor process conformance. Authorization establishes neither operational validity nor execution authorization. For `set_speed`, valid current-mode limits provide the process envelope.

## 3.5 Dynamic trust

Trust has identity, device, behavioral, historical, and contextual dimensions. With weights \(w_i\), the composite is \(T=\sum_i w_i t_i\), clipped to configured bounds; the frozen weights are \((0.20,0.25,0.25,0.15,0.15)\). For evidence magnitudes \(p_i,n_i\), each dimension updates as \(t_i' = \mathrm{clip}(t_i+r_i p_i-0.10 n_i)\), where \(r_i=0.01\) before a negative history and 0.005 afterwards. The known prior is 0.80, the unknown prior is 0.50, recency is 0.25, and historical confidence is 0.50. These are uncalibrated research parameters.

## 3.6 Threat evidence and risk

Threat evidence is deterministic and observable: authentication failure, authorization failure, operational constraint violation, repeated violation, and explicitly represented uncertainty conditions. The output is a security-signal score, not attack probability. Risk combines available threat evidence, distrust, criticality, and independent anomaly evidence using original weights 0.40, 0.25, 0.20, and 0.15, renormalizing over available components. It represents estimated danger under available evidence, not probability of attack.

## 3.7 Behavioral drift and governed adaptation

Drift is scoped to source-target-operation. After three comparable observations, a three-observation reference is compared with the current observation using normalized change score \(d=|x-\bar{x}_{ref}|/(u-l)\). The threshold is 0.30 and persistence requirement is two. Statuses distinguish insufficient history/scope, no change, transient deviation, known regime change, and unexplained persistent drift. Adaptation is gated: it requires known regime change, supported-valid semantics, execution/state-effect/operational feedback, and context-scope agreement. It does not automatically normalize unexplained drift.

## 3.8 Decision assurance

Assurance executes after autonomous-authority assessment and before planning. It consumes direct threat/correlation evidence, persistent unexplained drift, and corroborated trust degradation. It can restrict existing permissive authority or introduce `REQUEST_APPROVAL`; it cannot create autonomous authority. A valid known regime change is not treated as unexplained drift.

## 3.9 Planning, decision, governance, and execution

The action vocabulary is `ALLOW`, `MONITOR`, `LIMIT`, `REQUEST_APPROVAL`, `BLOCK`, and `ISOLATE`. Planning produces permissible candidates and decision selects a proposal. Governance independently checks context/proposal binding, planner membership, authorization, authority, operational validity, payload completeness, review requirements, and execution prerequisites. Its authorization artifact is required by execution, which uses exactly the authorized payload.

## 3.10 Outcome, memory, feedback, and provenance

Observed outcomes form experience records stored in episodic memory. Feedback is one-way in V1 and does not directly change inference or action selection. Traceability consists of evidence references, policy/model versions, decision and governance records, and execution outcomes; it is structured decision provenance rather than post-hoc neural explanation.

## 3.11 End-to-end pipeline

For each event, TAIOS validates the event; projects observable input; assesses semantics, drift, authorization, threat, correlation, trust, and risk; constructs context; assesses authority and assurance; plans and decides; governs and executes; records outcome, experience, and feedback; then evaluates governed adaptation. Figure 1 depicts the implemented architecture.
