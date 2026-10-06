# TAIOS

## Trust-Aware, Adaptive, and Explainable Autonomous Decision Intelligence for Industrial IoT

**TAIOS** is a research-oriented software architecture for bounded autonomous decision-making in Industrial Internet of Things (IIoT) environments.

The system combines contextual reasoning, dynamic trust assessment, security-risk evaluation, drift detection, governed adaptation, decision assurance, policy enforcement, human oversight, and capability-controlled execution within a reproducible multi-stage decision pipeline.

TAIOS is designed around a fundamental safety principle:

> **Decision intelligence does not imply execution authority.**

Intelligent and agentic components may interpret evidence, construct alternatives, and support decision formation, but process-changing actions remain subject to deterministic authorization, governance, state validation, and safety enforcement.

---

## Overview

Industrial autonomous systems must operate under changing process conditions, incomplete information, compromised entities, uncertain security evidence, and strict operational constraints.

TAIOS addresses this problem through a bounded decision architecture in which autonomous reasoning is separated from the authority required to modify an industrial process.

The end-to-end architecture follows the conceptual lifecycle:

```text
Industrial Event
      |
      v
Event Validation
      |
      v
Context Construction
      |
      +------------------+
      |                  |
      v                  v
Trust Assessment     Threat Evidence
      |                  |
      +--------+---------+
               |
               v
         Risk Assessment
               |
               v
        Drift Detection
               |
               v
      Decision Assurance
               |
               v
       Candidate Actions
               |
               v
    Bounded Decision Logic
               |
               v
          Governance
               |
        +------+------+
        |             |
        v             v
   Human Review   Autonomous Path
        |             |
        +------+------+
               |
               v
     Execution Authorization
               |
               v
      State / Mode Validation
               |
               v
        Safety Enforcement
               |
               v
         Process Outcome
               |
               v
 Experience / Feedback / Memory
```

Historical experience may improve future reasoning, but it cannot independently expand execution authority.

---

## Core Design Principles

TAIOS is built around the following engineering principles:

- **Bounded autonomy** — autonomous reasoning operates only within explicitly established authority.
- **Decision/execution separation** — producing a recommendation does not grant permission to execute it.
- **Evidence-aware reasoning** — trust, threat, risk, operational semantics, authorization, and drift are represented separately.
- **Fail-safe uncertainty handling** — missing information is not interpreted as evidence of safety or maliciousness.
- **Independent governance** — candidate decisions remain subject to policy and governance checks.
- **Context-bound execution** — authorization is valid only for the corresponding transaction and runtime state.
- **Deterministic safety enforcement** — process mutation remains protected by deterministic validation and safety mechanisms.
- **Causal adaptation** — adaptation uses observable evidence and cannot retroactively alter previous decisions.
- **Reproducibility** — deterministic event generation, experiment manifests, fingerprints, and seeded evaluation support repeatable experiments.
- **Auditability** — decision evidence, provenance, governance outcomes, execution results, and feedback remain reconstructable.

---

## Decision Vocabulary

TAIOS uses a fixed operational action vocabulary:

| Action | Meaning |
|---|---|
| `ALLOW` | Permit an eligible operation |
| `MONITOR` | Permit observation-oriented handling without stronger intervention |
| `LIMIT` | Restrict an operation to an explicitly authorized safe value or range |
| `REQUEST_APPROVAL` | Defer the operation for authoritative review |
| `BLOCK` | Prevent the requested operation |
| `ISOLATE` | Request isolation when explicitly supported by policy and execution capability |

The existence of an action in the vocabulary does not imply that every execution backend is authorized or capable of performing it.

---

## Architecture

TAIOS separates decision intelligence from process-changing authority.

### Decision and Evidence Layer

The decision layer contains:

- Event Manager
- Context Agent
- Trust Agent
- Threat Evidence Model
- Risk Agent
- Drift Detector
- Behavioral Adaptation
- Decision Assurance
- Planning Agent
- Decision Agent

These components construct and interpret decision evidence but do not directly mutate the industrial process.

### Governance Layer

The governance layer independently evaluates proposed decisions against:

- authorization state,
- policy constraints,
- operational semantics,
- available authority,
- human-review requirements,
- transaction consistency.

### Execution Layer

Execution occurs only after the required governance path succeeds.

The execution boundary verifies that the authorized operation still corresponds to the current transaction and system state before mutation is permitted.

This provides the architectural separation:

```text
Decision Intelligence
        |
        v
Governance
        |
        v
Execution Authorization
        |
        v
State / Mode Validation
        |
        v
Safety Enforcement
        |
        v
Industrial Process
```

---

## Trust Assessment

TAIOS maintains dynamic trust information using multiple evidence dimensions, including:

- identity evidence,
- device evidence,
- behavioral evidence,
- historical evidence,
- contextual evidence.

Trust is updated causally as new observable evidence becomes available.

A reduction in trust is **not**, by itself, treated as proof of malicious activity. Trust contributes to decision context and must be interpreted alongside independent operational and security evidence.

---

## Threat and Risk Assessment

TAIOS explicitly separates threat evidence from risk.

The threat subsystem derives observable security evidence from conditions such as:

- authentication failure,
- authorization failure,
- operational constraint violation,
- repeated operational violations,
- unresolved authorization,
- incomplete operational semantics.

The resulting security signal is an **uncalibrated evidence score**, not an attack probability.

Risk represents the potential danger associated with permitting or executing the current request. Available evidence may include:

- threat/security evidence,
- distrust,
- asset criticality,
- anomaly information.

Unavailable evidence is represented explicitly rather than silently replaced with a benign value.

---

## Drift Detection and Governed Adaptation

TAIOS distinguishes persistent behavioral change from known changes in industrial operating context.

The drift detector can represent states including:

- insufficient history,
- insufficient semantic scope,
- no change,
- transient deviation,
- known regime change,
- unexplained persistent drift.

This distinction is important because legitimate production changes should not automatically be interpreted as attacks.

Governed behavioral adaptation may update contextual reference information only when predefined evidence and feedback requirements are satisfied.

Adaptation cannot create execution authority or bypass governance.

---

## Experience, Feedback, and Memory

TAIOS maintains post-decision information through:

```text
Decision
   |
   v
Outcome
   |
   v
Experience
   |
   v
Feedback
   |
   v
Memory
   |
   v
Future Reasoning
```

Experience is informational rather than authoritative:

```text
Experience  ---> Better-Informed Reasoning

Experience  -X-> Additional Authority
```

A previously successful or approved operation therefore does not automatically become authorized in a later transaction.

---

## Experimental Scenarios

The deterministic scenario framework currently includes:

| Scenario | Purpose |
|---|---|
| `S1` | Normal industrial operation |
| `S2` | Compromised device behavior |
| `S3` | Credential compromise / unresolved operational semantics |
| `S4` | Conflicting evidence |
| `S5` | Legitimate operating-regime change / concept drift |
| `S6` | Coordinated security activity |

The scenario framework separates evaluator-only labels from information available to inference components.

Ground-truth labels, expected actions, scenario-design provenance, and evaluator metadata must not be consumed as decision features.

---

## Reproducible Experimentation

TAIOS experiments are deterministic with respect to their configured inputs.

Experiment identity includes information such as:

- scenario,
- random seed,
- event count,
- simulated start time,
- event interval,
- generator version,
- asset configuration,
- identity configuration.

Experiment artifacts include deterministic fingerprints that allow repeated runs to be compared.

Typical outputs are written under:

```text
logs/<experiment_id>/
```

and may include:

```text
experiment.json
scenario_manifest.json
events.jsonl
```

Evaluation artifacts are stored separately under the results directory.

---

## Repository Structure

A typical TAIOS repository layout is:

```text
TAIOS/
├── adaptation/          # Governed adaptation mechanisms
├── agents/              # Trust, risk, planning, decision, governance, execution
├── config/              # System and experimental configuration
├── core/                # Core contracts, pipeline, actions, state and assessments
├── docs/                # Architecture and milestone documentation
├── environment/         # Industrial assets, identities, events and state
├── evaluation/          # Experimental evaluation and metrics
├── intelligence/        # Trust, threat, risk, semantics and drift models
├── memory/              # Episodic, feedback and behavioral reference memory
├── results/             # Generated experimental outputs
├── tests/               # Unit, integration and invariant tests
├── main.py
├── requirements.txt
└── README.md
```

The exact structure may evolve as experimental components are extended.

---

## Installation

### Requirements

Recommended environment:

- Linux
- Python 3.14+
- Python virtual environment

Clone the repository and create an isolated environment:

```bash
git clone <repository-url>
cd TAIOS

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Quick Start

Run a deterministic scenario:

```bash
python main.py --scenario S1 --events 20 --seed 42
```

Example:

```bash
python main.py \
    --scenario S2 \
    --events 10 \
    --seed 42
```

The simulator uses deterministic experiment context so that the same configuration can be reproduced.

---

## Running Tests

Run the complete test suite with:

```bash
pytest -q
```

For development, individual test modules can also be executed:

```bash
pytest tests/test_trust.py -q
pytest tests/test_risk.py -q
pytest tests/test_governance.py -q
pytest tests/test_pipeline.py -q
```

A change should not be considered experimentally valid solely because the program executes successfully. Relevant unit, integration, causal, leakage-boundary, and reproducibility tests should also pass.

---

## Evaluation

TAIOS supports evaluation across multiple dimensions.

### Decision Quality

- exact decision agreement,
- unsafe autonomous action rate,
- false intervention rate,
- autonomous decision rate,
- human-review rate.

### Trust

- trust evolution,
- degradation under adverse evidence,
- recovery behavior,
- evidence coverage.

### Risk and Security Evidence

- evidence availability,
- risk evolution,
- security-signal response,
- uncertainty handling.

### Drift and Adaptation

- transient deviation detection,
- persistent drift detection,
- known-regime recognition,
- adaptation eligibility,
- adaptation latency,
- governed reference updates.

### Governance and Execution

- governance approval/rejection,
- approval requirements,
- execution success,
- stale-state rejection,
- replay prevention,
- unauthorized mutation prevention.

### Engineering

- deterministic reproducibility,
- transaction consistency,
- provenance completeness,
- failure handling,
- execution-path integrity.

---

## Experimental Baselines

The evaluation framework supports controlled configurations including:

- rule-based decision baseline,
- static TAIOS,
- adaptive TAIOS,
- TAIOS without dynamic trust influence.

Baseline comparisons reuse equivalent scenario streams while maintaining fresh system state for each experimental configuration.

This enables component-level and causal analysis without changing the underlying scenario evidence.

---

## Research Integrity

TAIOS enforces a strict separation between information available to the decision system and information reserved for experimental evaluation.

The following must not be used as inference features:

- ground-truth labels,
- expected safe actions,
- scenario identifiers used only for experimental design,
- evaluator-only provenance,
- future observations,
- post-hoc correctness labels.

This boundary is essential for avoiding label leakage and preserving the validity of experimental results.

---

## Operating Modes

TAIOS is designed around progressively stronger deployment authority:

```text
Simulation
    |
    v
Shadow
    |
    v
Supervised
    |
    v
Controlled Execution
```

These modes do not represent different reasoning architectures. They vary the maximum execution authority available at the industrial boundary.

`Simulation` and `Shadow` operation can therefore be used to evaluate decision behavior without granting process-changing authority.

---

## Safety and Scope

TAIOS is a **research prototype**.

It is not a certified industrial safety system, PLC safety controller, Safety Instrumented System (SIS), or replacement for independently engineered industrial protection mechanisms.

The current software should not be connected to safety-critical physical equipment without appropriate engineering controls, independent validation, authorization boundaries, hardware/process interlocks, and applicable industrial safety procedures.

Research results obtained from deterministic simulation or controlled software experiments should not be interpreted as evidence of production safety certification.

---

## Reproducibility

When modifying experimental behavior:

1. preserve deterministic execution where applicable;
2. update the corresponding model or generator version;
3. update or add tests;
4. regenerate affected evaluation artifacts;
5. verify that evaluator-only information remains isolated;
6. document changes that affect experimental interpretation.

Do not alter thresholds or policies retrospectively merely to obtain preferred experimental outcomes.

---

## Documentation

Detailed design and milestone documentation is maintained under:

```text
docs/
```

This includes specifications for trust, risk, decision authority, threat evidence, drift detection, adaptation, experimental baselines, and other architectural components.

The README intentionally provides the system-level view; implementation-specific scientific assumptions should remain documented close to the corresponding subsystem.


## Research Status

TAIOS is under active research development.

Current work focuses on evaluating whether trust-aware evidence processing, decision assurance, governed adaptation, bounded agentic reasoning, and independently enforced execution authority can support safer and more auditable autonomous decision-making in dynamic Industrial IoT environments.

Experimental findings should be interpreted within the scenarios, assumptions, evidence coverage, and execution capabilities explicitly documented by the project.
