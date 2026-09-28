from __future__ import annotations
import random
from dataclasses import asdict
from core.experiment import ExperimentRun, DEFAULT_SIMULATION_START, GENERATOR_VERSION, OBSERVABLE_GENERATOR_VERSION
from typing import List
from environment.assets import ASSET_REGISTRY, get_asset
from environment.identities import DEFAULT_IDENTITIES
from environment.event import IndustrialEvent
from environment.scenarios import get_scenario_manifest
from environment.provenance import EventProvenance
from environment.industrial_environment import IndustrialState, OperatingMode
from environment.operational_limits import OperationalLimits

class EventGenerator:
    def __init__(self, seed: int = 42, *, observable_state=False):
        if type(observable_state) is not bool:
            raise ValueError("observable_state must be bool")
        self.observable_state = observable_state
        self._industrial_state = IndustrialState()
        self.seed = seed
        self.rng = random.Random(seed)
        self._run = None
        self._sequence = 0
        self.assets = ASSET_REGISTRY
        self.operational_limits = OperationalLimits()

    @property
    def generator_version(self):
        return OBSERVABLE_GENERATOR_VERSION if self.observable_state else GENERATOR_VERSION

    def configuration_snapshot(self, scenario_id=None, n=100):
        config = {"assets": [a.to_dict() for a in self.assets.values()],
                "identities": [asdict(identity) for identity in DEFAULT_IDENTITIES],
                "initial_industrial_state": IndustrialState().to_dict(),
                "operational_limits": self.operational_limits.to_dict()}
        if self.observable_state:
            config["observable_state"] = True
        if scenario_id is not None:
            config["scenario_manifest"] = get_scenario_manifest(scenario_id, max(0, n)).to_dict()
        return config

    def create_run(self, scenario_id, n=100,
                   simulation_start_time=DEFAULT_SIMULATION_START, event_interval_seconds=1.0):
        return ExperimentRun(scenario_id, self.seed, max(0, n), simulation_start_time,
                             generator_version=self.generator_version,
                             event_interval_seconds=event_interval_seconds,
                             configuration=self.configuration_snapshot(scenario_id, n))

    def _event(self, **kwargs):
        if self.observable_state:
            snapshot = self._industrial_state.snapshot(kwargs['target_id']).to_dict()
            context = dict(kwargs.get('contextual_features', {}))
            context.update(production_state=snapshot['production_state'],
                           operating_mode=snapshot['operating_mode'], state_snapshot=snapshot)
            kwargs['contextual_features'] = context
        if self._run is not None:
            self._sequence += 1
            kwargs.update(self._run.event_metadata(self._sequence))
            kwargs['provenance'] = EventProvenance(
                self._run.experiment_id, self._manifest.scenario_id, self._manifest.scenario_version,
                self._run.generator_version, self._sequence, self._manifest.phase_at(self._sequence),
                self._manifest.transition_type, self._manifest.causal_tags_at(self._sequence),
                self._manifest.total_events)
        return IndustrialEvent(**kwargs)

    def generate(self, scenario_id: str, n: int = 100, experiment=None) -> List[IndustrialEvent]:
        run = experiment if experiment is not None else self.create_run(scenario_id, n)
        run.validate_identity()
        if (run.scenario_id, run.seed, run.total_events) != (scenario_id, self.seed, max(0, n)):
            raise ValueError("Experiment context does not match generation arguments")
        if run.generator_version != self.generator_version:
            raise ValueError("Experiment generator_version does not match this generator")
        if run.configuration != self.configuration_snapshot(scenario_id, n):
            raise ValueError("Experiment configuration does not match the current environment")
        self._manifest = get_scenario_manifest(scenario_id, max(0, n))
        self._industrial_state = IndustrialState()
        self.rng.seed(run.seed)
        self._run, self._sequence = run, 0
        try:
            return self._generate_scenario(scenario_id, n)
        finally:
            self._run = None

    def _normal(self, scenario_id="S1") -> IndustrialEvent:
        source = self.rng.choice([a for a in self.assets.values() if a.asset_type in {"PLC", "HMI", "service"}])
        target = self.rng.choice([a for a in self.assets.values() if a.asset_type == "actuator"])
        ident = self.rng.choice(DEFAULT_IDENTITIES)
        value = self.rng.randint(35, 75)
        return self._event(
            source_id=source.asset_id, source_type=source.asset_type,
            target_id=target.asset_id, target_type=target.asset_type,
            identity_id=ident.identity_id, event_type="control_command",
            operation="set_speed", requested_value=value,
            network_zone=source.network_zone, protocol=source.protocol,
            authentication_status=True, asset_criticality=target.criticality,
            contextual_features={"production_state": "ACTIVE", "anomaly_score": 0.05},
            ground_truth="BENIGN", expected_safe_action="ALLOW",
            scenario_id=scenario_id,
        )

    def _generate_scenario(self, scenario_id: str, n: int = 100) -> List[IndustrialEvent]:
        if n <= 0:
            return []
        if scenario_id == "S1":
            return [self._normal("S1") for _ in range(n)]
        if scenario_id == "S2":
            return self._compromised_device(n)
        if scenario_id == "S3":
            return self._credential_compromise(n)
        if scenario_id == "S4":
            return self._conflicting_evidence(n)
        if scenario_id == "S5":
            return self._concept_drift(n)
        if scenario_id == "S6":
            return self._coordinated_attack(n)
        if scenario_id == "S7":
            return self._stealthy_valid_compromise(n)
        if scenario_id == "S8":
            return self._legitimate_valid_shift(n)
        if scenario_id == "S9":
            return self._recovery_after_suspicion(n)
        raise ValueError(f"Unknown scenario: {scenario_id}")

    def _compromised_device(self, n):
        source = get_asset("PLC-07")
        target = get_asset("MOTOR-02")
        out = []
        compromise_at = (self._manifest.transition_sequence or n + 1) - 1
        for i in range(n):
            compromised = i >= compromise_at
            out.append(self._event(
                source_id=source.asset_id, source_type=source.asset_type,
                target_id=target.asset_id, target_type=target.asset_type,
                identity_id="operator-12", event_type="control_command",
                operation="set_speed",
                requested_value=self.rng.randint(90, 120) if compromised else self.rng.randint(40, 70),
                network_zone=source.network_zone, protocol=source.protocol,
                authentication_status=True, asset_criticality=target.criticality,
                contextual_features={
                    "production_state": "ACTIVE",
                    "anomaly_score": 0.92 if compromised else 0.05,
                    "compromise_phase": compromised,
                    "event_sequence": i + 1,
                    # One-based position at which the compromised phase begins.
                    "compromise_event": self._manifest.transition_sequence,
                },
                ground_truth="MALICIOUS" if compromised else "BENIGN",
                expected_safe_action="BLOCK" if compromised else "ALLOW",
                scenario_id="S2"))
        return out

    def _credential_compromise(self, n):
        source = get_asset("HMI-02")
        target = get_asset("PLC-03")
        out = []
        for i in range(n):
            malicious = self._manifest.phase_at(i + 1) == "POST_COMPROMISE"
            out.append(self._event(
                source_id=source.asset_id, source_type=source.asset_type,
                target_id=target.asset_id, target_type=target.asset_type,
                identity_id="operator-01", event_type="control_command",
                operation="write_register",
                requested_value=999 if malicious else 55,
                network_zone=source.network_zone, protocol=source.protocol,
                authentication_status=True, asset_criticality=target.criticality,
                contextual_features={"production_state":"ACTIVE",
                                     "anomaly_score":0.88 if malicious else 0.04,
                                     "valid_credentials": True},
                ground_truth="MALICIOUS" if malicious else "BENIGN",
                expected_safe_action="BLOCK" if malicious else "ALLOW",
                scenario_id="S3"))
        return out

    def _conflicting_evidence(self, n):
        source = get_asset("PLC-03")
        target = get_asset("MOTOR-02")
        return [self._event(
            source_id=source.asset_id, source_type=source.asset_type,
            target_id=target.asset_id, target_type=target.asset_type,
            identity_id="engineer-03", event_type="control_command",
            operation="set_speed", requested_value=84,
            network_zone=source.network_zone, protocol=source.protocol,
            authentication_status=True, asset_criticality=target.criticality,
            contextual_features={"production_state":"ACTIVE","anomaly_score":0.67,
                                 "prior_device_trust":0.91,"simulated_attack_probability":0.76},
            ground_truth="SUSPICIOUS", expected_safe_action="REQUEST_APPROVAL",
            scenario_id="S4") for _ in range(n)]

    def _concept_drift(self, n):
        source = get_asset("PLC-01")
        target = get_asset("MOTOR-02")
        out = []
        state = self._industrial_state if self.observable_state else IndustrialState()
        drift_at = (self._manifest.transition_sequence or n + 1) - 1
        for i in range(n):
            after = i >= drift_at
            if i == drift_at:
                state.set_operating_mode(OperatingMode.HIGH_OUTPUT)
            value = self.rng.randint(82, 94) if after else self.rng.randint(45, 70)
            limit = self.operational_limits.check_operational_limit(
                target.asset_id, "set_speed", value, state.operating_mode)
            # Snapshot is pre-command context; this step does not execute commands.
            snapshot = state.snapshot(target.asset_id).to_dict()
            out.append(self._event(
                source_id=source.asset_id, source_type=source.asset_type,
                target_id=target.asset_id, target_type=target.asset_type,
                identity_id="operator-01", event_type="control_command",
                operation="set_speed",
                requested_value=value,
                network_zone=source.network_zone, protocol=source.protocol,
                authentication_status=True, asset_criticality=target.criticality,
                contextual_features={"production_state":"ACTIVE","anomaly_score":0.65 if after else 0.05,
                                     "drift_phase": "post" if after else "pre",
                                     "new_operating_regime": after,
                                     "regime_change_sequence": drift_at + 1 if drift_at < n else None,
                                     "operating_mode": state.operating_mode.value,
                                     "state_snapshot": snapshot,
                                     "operational_limit": limit.to_dict()},
                ground_truth="BENIGN", expected_safe_action="ALLOW",
                scenario_id="S5"))
        return out

    def _coordinated_attack(self, n):
        attackers = [get_asset(asset_id) for asset_id in ("HMI-02", "PLC-04", "SERVICE-03")]
        target = get_asset("PLC-03")
        out = []
        attack_at = (self._manifest.transition_sequence or n + 1) - 1
        for i in range(n):
            if i < attack_at:
                out.append(self._normal("S6"))
            else:
                source = attackers[i % len(attackers)]
                out.append(self._event(
                    source_id=source.asset_id, source_type=source.asset_type,
                    target_id=target.asset_id, target_type=target.asset_type,
                    identity_id="user-17", event_type="control_command",
                    operation="write_register", requested_value=self.rng.randint(900,999),
                    network_zone=source.network_zone, protocol=source.protocol,
                    authentication_status=True, asset_criticality=target.criticality,
                    contextual_features={"production_state":"ACTIVE","anomaly_score":0.79,
                                         "coordination_group":"CG-01"},
                    ground_truth="MALICIOUS", expected_safe_action="ISOLATE",
                    scenario_id="S6"))
        return out

    def _valid_speed_event(self, source, target, value, scenario_id, expected_action, *, mode="NORMAL"):
        return self._event(
            source_id=source.asset_id, source_type=source.asset_type,
            target_id=target.asset_id, target_type=target.asset_type,
            identity_id="operator-12", event_type="control_command", operation="set_speed",
            requested_value=value, network_zone=source.network_zone, protocol=source.protocol,
            authentication_status=True, asset_criticality=target.criticality,
            # Only allowlisted production/mode context can reach inference.
            contextual_features={"production_state": "ACTIVE", "operating_mode": mode},
            ground_truth="SUSPICIOUS" if expected_action == "REQUEST_APPROVAL" else "BENIGN",
            expected_safe_action=expected_action, scenario_id=scenario_id)

    def _stealthy_valid_compromise(self, n):
        source, target, out = get_asset("PLC-07"), get_asset("MOTOR-02"), []
        transition = (self._manifest.transition_sequence or n + 1) - 1
        for i in range(n):
            suspicious = i >= transition
            value = self.rng.randint(72, 78) if suspicious else self.rng.randint(35, 45)
            out.append(self._valid_speed_event(source, target, value, "S7",
                                               "REQUEST_APPROVAL" if suspicious else "ALLOW"))
        return out

    def _legitimate_valid_shift(self, n):
        source, target, out = get_asset("PLC-01"), get_asset("MOTOR-02"), []
        transition = (self._manifest.transition_sequence or n + 1) - 1
        for i in range(n):
            changed = i >= transition
            if i == transition:
                self._industrial_state.set_operating_mode(OperatingMode.HIGH_OUTPUT)
            out.append(self._valid_speed_event(source, target,
                                               self.rng.randint(72, 88) if changed else self.rng.randint(35, 45),
                                               "S8", "ALLOW", mode="HIGH_OUTPUT" if changed else "NORMAL"))
        return out

    def _recovery_after_suspicion(self, n):
        source, target, out = get_asset("PLC-07"), get_asset("MOTOR-02"), []
        transitions = self._manifest.transition_sequence or (n + 1, n + 1)
        if type(transitions) is int:
            transitions = (transitions, n + 1)
        suspicious_start, recovery_start = transitions
        for i in range(n):
            suspicious = suspicious_start - 1 <= i < recovery_start - 1
            value = self.rng.randint(72, 78) if suspicious else self.rng.randint(35, 45)
            out.append(self._valid_speed_event(source, target, value, "S9",
                                               "REQUEST_APPROVAL" if suspicious else "ALLOW"))
        return out
