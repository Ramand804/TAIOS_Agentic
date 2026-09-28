SCENARIOS = {
    "S1": "Normal industrial operation",
    "S2": "Previously trusted device becomes compromised",
    "S3": "Valid credentials are used maliciously",
    "S4": "Threat, trust and criticality provide conflicting evidence",
    "S5": "Legitimate operating behavior changes over time",
    "S6": "Multiple entities participate in coordinated malicious activity",
    "S7": "Stealthy valid behavioral compromise evaluation scenario",
    "S8": "Legitimate valid behavioral shift negative-control scenario",
    "S9": "Recovery after suspicious valid behavioral shift evaluation scenario",
}

from dataclasses import asdict, dataclass
from environment.assets import get_asset

SCENARIO_VERSION = "day1c-step4-v1"
EXTENDED_SCENARIO_VERSION = "milestone8c-extended-scenarios-v1"

# name, transition type, ordered phases, affected assets, labeling policy
SCENARIO_DESIGNS = {
    "S1": ("normal_operation", "NONE", ("NORMAL",),
           (), "All events BENIGN / ALLOW."),
    "S2": ("compromised_device", "DEVICE_COMPROMISE", ("PRE_COMPROMISE", "POST_COMPROMISE"),
           ("PLC-07", "MOTOR-02"), "Pre: BENIGN / ALLOW; post: MALICIOUS / BLOCK."),
    "S3": ("credential_compromise", "CREDENTIAL_COMPROMISE", ("PRE_COMPROMISE", "POST_COMPROMISE"),
           ("HMI-02", "PLC-03"), "Authentication succeeds in both phases; pre BENIGN / ALLOW, post MALICIOUS / BLOCK."),
    "S4": ("conflicting_evidence", "NONE", ("CONFLICTING_EVIDENCE",),
           ("PLC-03", "MOTOR-02"), "SUSPICIOUS / REQUEST_APPROVAL are experimental labels, not inferred decisions."),
    "S5": ("legitimate_regime_change", "OPERATING_REGIME_CHANGE", ("PRE_CHANGE", "POST_CHANGE"),
           ("PLC-01", "MOTOR-02"), "NORMAL to HIGH_OUTPUT; both phases BENIGN / ALLOW."),
    "S6": ("coordinated_attack", "COORDINATED_ATTACK", ("PRE_ATTACK", "POST_ATTACK"),
           ("HMI-02", "PLC-04", "SERVICE-03", "PLC-03"), "Pre: BENIGN / ALLOW; post: MALICIOUS / ISOLATE."),
}

# These definitions are frozen evaluator-facing scenario contracts.  They are
# deliberately not copied into runtime observations.
EXTENDED_SCENARIO_DESIGNS = {
    "S7": ("stealthy_valid_compromise", "BEHAVIORAL_SHIFT", ("BASELINE", "SUSPICIOUS_VALID"),
           ("PLC-07", "MOTOR-02"), "Baseline routine commands followed by valid unexplained high-end commands."),
    "S8": ("legitimate_valid_behavioral_shift", "OPERATING_REGIME_CHANGE", ("BASELINE", "EXPLAINED_HIGH_OUTPUT"),
           ("PLC-01", "MOTOR-02"), "Valid high-output commands follow an explicit observable operating-mode change."),
    "S9": ("recovery_after_suspicious_period", "BEHAVIORAL_SHIFT_AND_RECOVERY", ("BASELINE", "SUSPICIOUS_VALID", "RECOVERY"),
           ("PLC-07", "MOTOR-02"), "Valid unexplained shift is followed by a return to the prior valid pattern."),
}


@dataclass(frozen=True)
class ScenarioEvaluationMetadata:
    scenario_id: str
    scenario_version: str
    purpose: str
    event_count: int
    phase_boundaries: tuple[int, ...]
    annotation_rationale: str
    expected_behavioral_property: str

    def to_dict(self):
        return {"scenario_id": self.scenario_id, "scenario_version": self.scenario_version,
                "purpose": self.purpose, "event_count": self.event_count,
                "phase_boundaries": list(self.phase_boundaries),
                "annotation_rationale": self.annotation_rationale,
                "expected_behavioral_property": self.expected_behavioral_property}


@dataclass(frozen=True)
class ScenarioManifest:
    scenario_id: str
    name: str
    description: str
    scenario_version: str
    total_events: int
    transition_sequence: int | None
    phases: tuple[str, ...]
    affected_entities: tuple[str, ...]
    transition_type: str
    ground_truth_policy: str

    def __post_init__(self):
        if self.scenario_id not in SCENARIO_DESIGNS and self.scenario_id not in EXTENDED_SCENARIO_DESIGNS:
            raise ValueError(f"Unknown scenario: {self.scenario_id}")
        if type(self.total_events) is not int or self.total_events < 0:
            raise ValueError("total_events must be a nonnegative integer")
        for key in ('name', 'description', 'scenario_version', 'transition_type', 'ground_truth_policy'):
            if not isinstance(getattr(self, key), str) or not getattr(self, key).strip():
                raise ValueError(f"{key} must be a nonempty string")
        object.__setattr__(self, 'phases', tuple(self.phases))
        object.__setattr__(self, 'affected_entities', tuple(self.affected_entities))
        if not self.phases or any(not isinstance(p, str) or not p.strip() for p in self.phases):
            raise ValueError("phases must contain nonempty names")
        if len(set(self.phases)) != len(self.phases) or len(self.phases) > 3:
            raise ValueError("This model supports at most three distinct phases")
        for asset_id in self.affected_entities:
            get_asset(asset_id)
        if self.transition_sequence is not None:
            transitions = ((self.transition_sequence,) if type(self.transition_sequence) is int
                           else tuple(self.transition_sequence))
            if (len(transitions) != len(self.phases) - 1 or
                    any(type(value) is not int or not 2 <= value <= self.total_events for value in transitions) or
                    tuple(sorted(transitions)) != transitions):
                raise ValueError("transition_sequence must mark each later phase")
        if (self.transition_type == 'NONE') != (len(self.phases) == 1):
            raise ValueError("Transition type must agree with the number of phases")
        if len(self.phases) == 2 and self.total_events >= 2 and self.transition_sequence is None:
            raise ValueError("A two-phase run with at least two events needs a transition")

    def phase_at(self, sequence_number):
        if type(sequence_number) is not int or not 1 <= sequence_number <= self.total_events:
            raise ValueError("Sequence number is outside the manifest")
        if self.transition_sequence is None:
            return self.phases[0]
        transitions = ((self.transition_sequence,) if type(self.transition_sequence) is int
                       else tuple(self.transition_sequence))
        return self.phases[sum(sequence_number >= boundary for boundary in transitions)]

    def causal_tags_at(self, sequence_number):
        return (self.name, self.phase_at(sequence_number).lower())

    def to_dict(self):
        result = asdict(self)
        result['phases'] = list(self.phases)
        result['affected_entities'] = list(self.affected_entities)
        if isinstance(self.transition_sequence, tuple):
            result['transition_sequence'] = list(self.transition_sequence)
        return result


def get_scenario_manifest(scenario_id, total_events):
    if scenario_id not in SCENARIO_DESIGNS and scenario_id not in EXTENDED_SCENARIO_DESIGNS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    name, transition_type, phases, entities, policy = (SCENARIO_DESIGNS.get(scenario_id) or
                                                        EXTENDED_SCENARIO_DESIGNS[scenario_id])
    transition = None
    if len(phases) == 2:
        candidate = max(1, total_events // (3 if scenario_id == 'S6' else 2)) + 1
        if candidate <= total_events:
            transition = candidate
    elif len(phases) == 3 and total_events >= 3:
        transition = (max(1, total_events // 4) + 1, max(2, total_events * 3 // 5) + 1)
    version = EXTENDED_SCENARIO_VERSION if scenario_id in EXTENDED_SCENARIO_DESIGNS else SCENARIO_VERSION
    return ScenarioManifest(scenario_id, name, SCENARIOS[scenario_id], version,
                            total_events, transition, phases, entities, transition_type, policy)


def get_scenario_evaluation_metadata(scenario_id, total_events):
    manifest = get_scenario_manifest(scenario_id, total_events)
    if scenario_id == 'S7':
        rationale = 'ALLOW during baseline; REQUEST_APPROVAL during suspicious valid commands as a conservative evaluator annotation.'
        property_ = 'Unexplained valid behavioral shift can be observed without changing authentication, authorization, or limits.'
    elif scenario_id == 'S8':
        rationale = 'ALLOW in both phases because the observable operating-mode change explains valid high-output commands.'
        property_ = 'A legitimate contextual shift should not be treated as suspicious solely because values change.'
    elif scenario_id == 'S9':
        rationale = 'ALLOW baseline and recovery; REQUEST_APPROVAL during the evaluator-defined suspicious period.'
        property_ = 'The frozen system may be observed for recovery after a valid unexplained shift.'
    else:
        rationale, property_ = manifest.ground_truth_policy, 'Existing scenario contract.'
    transitions = () if manifest.transition_sequence is None else (
        (manifest.transition_sequence,) if type(manifest.transition_sequence) is int else tuple(manifest.transition_sequence))
    return ScenarioEvaluationMetadata(scenario_id, manifest.scenario_version, manifest.name,
                                      total_events, transitions, rationale, property_)
