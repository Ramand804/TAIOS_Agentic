SCENARIOS = {
    "S1": "Normal industrial operation",
    "S2": "Previously trusted device becomes compromised",
    "S3": "Valid credentials are used maliciously",
    "S4": "Threat, trust and criticality provide conflicting evidence",
    "S5": "Legitimate operating behavior changes over time",
    "S6": "Multiple entities participate in coordinated malicious activity",
}

from dataclasses import asdict, dataclass
from environment.assets import get_asset

SCENARIO_VERSION = "day1c-step4-v1"

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
        if self.scenario_id not in SCENARIO_DESIGNS:
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
        if len(set(self.phases)) != len(self.phases) or len(self.phases) > 2:
            raise ValueError("This model supports one phase or two distinct phases")
        for asset_id in self.affected_entities:
            get_asset(asset_id)
        if self.transition_sequence is not None:
            if (type(self.transition_sequence) is not int or
                    not 2 <= self.transition_sequence <= self.total_events or len(self.phases) != 2):
                raise ValueError("transition_sequence must be the first event of the second phase")
        if (self.transition_type == 'NONE') != (len(self.phases) == 1):
            raise ValueError("Transition type must agree with the number of phases")
        if len(self.phases) == 2 and self.total_events >= 2 and self.transition_sequence is None:
            raise ValueError("A two-phase run with at least two events needs a transition")

    def phase_at(self, sequence_number):
        if type(sequence_number) is not int or not 1 <= sequence_number <= self.total_events:
            raise ValueError("Sequence number is outside the manifest")
        return self.phases[1] if self.transition_sequence is not None and sequence_number >= self.transition_sequence else self.phases[0]

    def causal_tags_at(self, sequence_number):
        return (self.name, self.phase_at(sequence_number).lower())

    def to_dict(self):
        result = asdict(self)
        result['phases'] = list(self.phases)
        result['affected_entities'] = list(self.affected_entities)
        return result


def get_scenario_manifest(scenario_id, total_events):
    if scenario_id not in SCENARIO_DESIGNS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    name, transition_type, phases, entities, policy = SCENARIO_DESIGNS[scenario_id]
    transition = None
    if len(phases) == 2:
        candidate = max(1, total_events // (3 if scenario_id == 'S6' else 2)) + 1
        if candidate <= total_events:
            transition = candidate
    return ScenarioManifest(scenario_id, name, SCENARIOS[scenario_id], SCENARIO_VERSION,
                            total_events, transition, phases, entities, transition_type, policy)
