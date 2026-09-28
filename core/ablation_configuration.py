"""Frozen-policy Milestone-8D configuration definitions."""
from dataclasses import dataclass
from enum import Enum

from core.drift_assessment import DriftAssessment, DriftStatus
from core.experiment import fingerprint


class AblationConfiguration(str, Enum):
    FULL_STATIC = 'FULL_STATIC'
    FULL_ADAPTIVE = 'FULL_ADAPTIVE'
    NO_ASSURANCE = 'NO_ASSURANCE'
    NO_DRIFT = 'NO_DRIFT'
    NO_ADAPT = 'NO_ADAPT'
    NO_TRUST = 'NO_TRUST'
    RULE_BASED = 'RULE_BASED'


@dataclass(frozen=True)
class AblationSpec:
    name: AblationConfiguration
    differs_from_full: tuple[str, ...]
    valid: bool = True
    rationale: str = ''

    @property
    def fingerprint(self):
        return fingerprint({'name': self.name.value, 'differs_from_full': self.differs_from_full,
                            'valid': self.valid, 'rationale': self.rationale})


SPECS = {
    AblationConfiguration.FULL_STATIC: AblationSpec(AblationConfiguration.FULL_STATIC, (), rationale='Frozen full static TAIOS.'),
    AblationConfiguration.FULL_ADAPTIVE: AblationSpec(AblationConfiguration.FULL_ADAPTIVE, ('governed adaptation enabled',)),
    AblationConfiguration.NO_ASSURANCE: AblationSpec(AblationConfiguration.NO_ASSURANCE, ('assurance gate disabled',)),
    AblationConfiguration.NO_DRIFT: AblationSpec(AblationConfiguration.NO_DRIFT, ('drift evidence unavailable to downstream consumers',)),
    AblationConfiguration.NO_ADAPT: AblationSpec(AblationConfiguration.NO_ADAPT, ('alias of static reference mode',)),
    AblationConfiguration.NO_TRUST: AblationSpec(AblationConfiguration.NO_TRUST, ('fixed neutral trust 0.80',)),
    AblationConfiguration.RULE_BASED: AblationSpec(AblationConfiguration.RULE_BASED, ('frozen rule decision/planning adapters',)),
}


class DriftUnavailableAdapter:
    """Experimental channel removal, explicitly reporting unavailable evidence.

    This adapter is not the frozen detector and does not assert NO_CHANGE.
    """
    version = 'milestone8d-drift-unavailable-adapter-v1'

    def __init__(self, configuration_fingerprint):
        self.configuration_fingerprint = configuration_fingerprint

    def reset(self):
        pass

    def _checkpoint(self):
        return None

    def _restore(self, checkpoint):
        pass

    def assess(self, observation, semantics, *, event_reference=None):
        scope = f'{observation["source_id"]}|{observation["target_id"]}|{observation["operation"]}'
        return DriftAssessment(event_reference=event_reference or fingerprint(observation), scope=scope,
            status=DriftStatus.INSUFFICIENT_SEMANTIC_SCOPE, evidence=(), history_count=0,
            reference_window_size=0, recent_window_size=0, change_score=0.0, persistence_count=0,
            context_explanation=None, unresolved_requirements=('Experimental ablation: drift evidence channel unavailable.',),
            model_version=self.version, configuration_fingerprint=self.configuration_fingerprint)


def create_ablation_pipeline(configuration):
    """Create only valid controlled variants; governance bypass is intentionally absent.

    NO_GOVERNANCE is methodologically invalid because PipelineResult and execution
    require a bound governance authorization artifact; removing it would weaken the
    independent execution safety contract rather than isolate a decision layer.
    """
    from adaptation.behavioral_adapter import BehavioralAdapter
    from agents.fixed_neutral_trust_agent import FixedNeutralTrustAgent
    from agents.rule_based_decision_agent import RuleBasedDecisionAgent
    from agents.rule_based_planning_agent import RuleBasedPlanningAgent
    from core.behavioral_reference import AdaptationMode
    from core.taios_pipeline import TAIOSPipeline
    configuration = AblationConfiguration(configuration)
    if configuration == AblationConfiguration.RULE_BASED:
        return TAIOSPipeline(planning_agent=RuleBasedPlanningAgent(), decision_agent=RuleBasedDecisionAgent(),
                             adaptation_mode=AdaptationMode.STATIC, assurance_enabled=False)
    kwargs = {'adaptation_mode': AdaptationMode.ADAPTIVE if configuration == AblationConfiguration.FULL_ADAPTIVE else AdaptationMode.STATIC}
    if configuration == AblationConfiguration.NO_ASSURANCE:
        kwargs['assurance_enabled'] = False
    if configuration == AblationConfiguration.NO_TRUST:
        kwargs['trust_agent'] = FixedNeutralTrustAgent()
    if configuration == AblationConfiguration.NO_DRIFT:
        kwargs['drift_detector'] = DriftUnavailableAdapter(SPECS[configuration].fingerprint)
    return TAIOSPipeline(**kwargs)
