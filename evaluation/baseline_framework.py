"""Factories for isolated Milestone-8A experimental configurations."""
from agents.fixed_neutral_trust_agent import FixedNeutralTrustAgent, NO_TRUST_VERSION
from agents.rule_based_decision_agent import RULE_BASELINE_VERSION, RuleBasedDecisionAgent
from agents.rule_based_planning_agent import RuleBasedPlanningAgent
from core.behavioral_reference import AdaptationMode
from core.experimental_configuration import (
    ExperimentalConfiguration, ExperimentalConfigurationSpec,
)
from core.taios_pipeline import TAIOSPipeline


SHARED = ('event stream', 'initial industrial state', 'operational semantics',
          'authorization', 'governance', 'execution', 'formal evaluator')

CONFIGURATION_SPECS = {
    ExperimentalConfiguration.RULE_BASED: ExperimentalConfigurationSpec(
        configuration=ExperimentalConfiguration.RULE_BASED,
        version=RULE_BASELINE_VERSION,
        differing_components=('observable-fact rule decision adapter',),
        shared_components=SHARED,
        rationale='Transparent deterministic comparison without evaluator labels.'),
    ExperimentalConfiguration.TAIOS_STATIC: ExperimentalConfigurationSpec(
        configuration=ExperimentalConfiguration.TAIOS_STATIC,
        version='milestone7d-pipeline-v1-static',
        differing_components=('behavioral adaptation disabled',),
        shared_components=SHARED,
        rationale='Frozen full TAIOS with STATIC behavioral references.'),
    ExperimentalConfiguration.TAIOS_ADAPTIVE: ExperimentalConfigurationSpec(
        configuration=ExperimentalConfiguration.TAIOS_ADAPTIVE,
        version='milestone7d-pipeline-v1-adaptive',
        differing_components=('governed behavioral adaptation enabled',),
        shared_components=SHARED,
        rationale='Frozen full TAIOS with governed contextual references.'),
    ExperimentalConfiguration.TAIOS_NO_TRUST: ExperimentalConfigurationSpec(
        configuration=ExperimentalConfiguration.TAIOS_NO_TRUST,
        version=NO_TRUST_VERSION,
        differing_components=('dynamic trust replaced by fixed 0.80 known-entity prior',),
        shared_components=SHARED,
        rationale='Controlled trust ablation using the documented canonical prior.'),
}


def create_pipeline(configuration):
    configuration = ExperimentalConfiguration(configuration)
    if configuration == ExperimentalConfiguration.RULE_BASED:
        return TAIOSPipeline(
            planning_agent=RuleBasedPlanningAgent(), decision_agent=RuleBasedDecisionAgent(),
            adaptation_mode=AdaptationMode.STATIC)
    if configuration == ExperimentalConfiguration.TAIOS_ADAPTIVE:
        return TAIOSPipeline(adaptation_mode=AdaptationMode.ADAPTIVE)
    if configuration == ExperimentalConfiguration.TAIOS_NO_TRUST:
        return TAIOSPipeline(
            trust_agent=FixedNeutralTrustAgent(), adaptation_mode=AdaptationMode.STATIC)
    return TAIOSPipeline(adaptation_mode=AdaptationMode.STATIC)
