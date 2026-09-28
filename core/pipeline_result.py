"""Immutable deterministic result contracts for the integrated TAIOS pipeline."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from core.decision_contracts import Record, export, freeze
from core.experiment import fingerprint
from environment.industrial_environment import IndustrialState


@dataclass(frozen=True, kw_only=True)
class PipelineFailure(Record):
    stage: str
    error_type: str
    reason: str
    event_reference: str | None
    state_reference: str
    pipeline_version: str


class PipelineProcessingError(RuntimeError):
    def __init__(self, failure):
        if type(failure) is not PipelineFailure:
            raise TypeError('Expected PipelineFailure')
        self.failure = failure
        super().__init__(f'{failure.stage}: {failure.reason}')


@dataclass(frozen=True, kw_only=True)
class PipelineResult(Record):
    event_id: str
    sequence_number: int | None
    event_reference: str
    observable_input: object
    trust_assessment: object
    risk_assessment: object
    authorization_assessment: object
    operational_semantic_assessment: object
    drift_assessment: object
    threat_assessment: object
    correlation_assessment: object
    authority_assessment: object
    decision_context: object
    planning_result: object
    proposed_decision: object
    governance_decision: object
    execution_result: object
    observed_outcome: object
    experience_reference: str
    feedback_reference: str
    input_state_reference: str
    state_before: IndustrialState
    state_after: IndustrialState
    regime_transition_applied: bool
    pipeline_version: str
    adaptation_proposal: object | None = None
    adaptation_decision: object | None = None
    behavioral_reference_used: str | None = None
    assurance_assessment: object | None = None
    assured_authority_assessment: object | None = None

    def __post_init__(self):
        object.__setattr__(self, 'observable_input', freeze(self.observable_input))
        if type(self.state_before) is not IndustrialState or type(self.state_after) is not IndustrialState:
            raise ValueError('Pipeline states must be IndustrialState')
        if type(self.regime_transition_applied) is not bool:
            raise ValueError('regime_transition_applied must be bool')
        if not isinstance(self.experience_reference, str) or not self.experience_reference:
            raise ValueError('experience_reference must be nonempty text')
        if not isinstance(self.feedback_reference, str) or not self.feedback_reference:
            raise ValueError('feedback_reference must be nonempty text')
        if self.decision_context.observation != self.observable_input:
            raise ValueError('Context observation is not the pipeline observation')
        if self.decision_context.operational_semantic_assessment != self.operational_semantic_assessment:
            raise ValueError('Context semantic assessment is not the pipeline assessment')
        if self.drift_assessment.event_reference != self.event_reference:
            raise ValueError('Drift assessment/event chain mismatch')
        if (self.adaptation_proposal is None) != (self.adaptation_decision is None):
            raise ValueError('Adaptation proposal and decision must be supplied together')
        if self.adaptation_proposal is not None:
            if self.adaptation_proposal.trigger_drift_reference != self.drift_assessment.reference:
                raise ValueError('Adaptation/drift chain mismatch')
            if self.adaptation_decision.proposal_reference != self.adaptation_proposal.reference:
                raise ValueError('Adaptation decision/proposal chain mismatch')
        if self.behavioral_reference_used is not None and not self.behavioral_reference_used:
            raise ValueError('behavioral_reference_used must be nonempty text')
        if (self.assurance_assessment is None) != (self.assured_authority_assessment is None):
            raise ValueError('Assurance and assured authority must be supplied together')
        if self.assurance_assessment is not None:
            if self.assurance_assessment.event_reference != self.event_reference:
                raise ValueError('Assurance/event chain mismatch')
            if self.assurance_assessment.authority_reference != self.authority_assessment.reference:
                raise ValueError('Assurance/existing-authority chain mismatch')
            if self.decision_context.autonomous_authority_assessment != self.assured_authority_assessment:
                raise ValueError('Planning context does not use assured authority')
        if self.correlation_assessment.current_event_reference != self.event_reference:
            raise ValueError('Correlation assessment/event chain mismatch')
        if self.planning_result.context_fingerprint != self.decision_context.reference:
            raise ValueError('Plan/context chain mismatch')
        if self.proposed_decision.planning_reference != self.planning_result.reference:
            raise ValueError('Proposal/plan chain mismatch')
        if self.governance_decision.proposal_reference != self.proposed_decision.reference:
            raise ValueError('Governance/proposal chain mismatch')
        if self.execution_result.governance_reference != self.governance_decision.reference:
            raise ValueError('Execution/governance chain mismatch')
        if self.execution_result.resulting_state.to_dict() != self.state_after.to_dict():
            raise ValueError('Execution result/state-after mismatch')
        if self.observed_outcome.event_reference != self.event_reference:
            raise ValueError('Outcome/event chain mismatch')
        if self.observed_outcome.execution_reference != self.execution_result.reference:
            raise ValueError('Outcome/execution chain mismatch')

    @property
    def pipeline_fingerprint(self):
        return fingerprint({
            'event_reference': self.event_reference,
            'context_reference': self.decision_context.reference,
            'threat_assessment_reference': self.threat_assessment.reference,
            'drift_assessment_reference': self.drift_assessment.reference,
            'correlation_assessment_reference': self.correlation_assessment.reference,
            'planning_reference': self.planning_result.reference,
            'proposal_reference': self.proposed_decision.reference,
            'governance_reference': self.governance_decision.reference,
            'execution_reference': self.execution_result.reference,
            'outcome_reference': self.observed_outcome.reference,
            'experience_reference': self.experience_reference,
            'feedback_reference': self.feedback_reference,
            'adaptation_proposal_reference': (
                self.adaptation_proposal.reference if self.adaptation_proposal else None),
            'adaptation_decision_reference': (
                self.adaptation_decision.reference if self.adaptation_decision else None),
            'behavioral_reference_used': self.behavioral_reference_used,
            'assurance_assessment_reference': (
                self.assurance_assessment.reference if self.assurance_assessment else None),
            'assured_authority_reference': (
                self.assured_authority_assessment.reference
                if self.assured_authority_assessment else None),
            'input_state_reference': self.input_state_reference,
            'state_before_reference': fingerprint(self.state_before.to_dict()),
            'state_after_reference': fingerprint(self.state_after.to_dict()),
            'pipeline_version': self.pipeline_version,
        })

    def to_dict(self):
        return {
            'event_id': self.event_id,
            'sequence_number': self.sequence_number,
            'event_reference': self.event_reference,
            'observable_input': export(self.observable_input),
            'trust_assessment': self.trust_assessment.to_inference_dict(),
            'risk_assessment': self.risk_assessment.to_inference_dict(),
            'authorization_assessment': self.authorization_assessment.to_dict(),
            'operational_semantic_assessment': self.operational_semantic_assessment.to_dict(),
            'drift_assessment': self.drift_assessment.to_dict(),
            'threat_assessment': self.threat_assessment.to_dict(),
            'correlation_assessment': self.correlation_assessment.to_dict(),
            'authority_assessment': self.authority_assessment.to_dict(),
            'decision_context': self.decision_context.to_dict(),
            'planning_result': self.planning_result.to_dict(),
            'proposed_decision': self.proposed_decision.to_dict(),
            'governance_decision': self.governance_decision.to_dict(),
            'execution_result': self.execution_result.to_dict(),
            'observed_outcome': self.observed_outcome.to_dict(),
            'experience_reference': self.experience_reference,
            'feedback_reference': self.feedback_reference,
            'adaptation_proposal': (
                self.adaptation_proposal.to_dict() if self.adaptation_proposal else None),
            'adaptation_decision': (
                self.adaptation_decision.to_dict() if self.adaptation_decision else None),
            'behavioral_reference_used': self.behavioral_reference_used,
            'assurance_assessment': (
                self.assurance_assessment.to_dict() if self.assurance_assessment else None),
            'assured_authority_assessment': (
                self.assured_authority_assessment.to_dict()
                if self.assured_authority_assessment else None),
            'input_state_reference': self.input_state_reference,
            'state_before': self.state_before.to_dict(),
            'state_after': self.state_after.to_dict(),
            'regime_transition_applied': self.regime_transition_applied,
            'pipeline_version': self.pipeline_version,
            'pipeline_fingerprint': self.pipeline_fingerprint,
        }


@dataclass(frozen=True, kw_only=True)
class EpisodeResult(Record):
    scenario_reference: str
    scenario_id: str
    seed: int | None
    pipeline_results: tuple[PipelineResult, ...]
    initial_state_reference: str
    final_state_reference: str
    structural_summary: object
    experience_count: int
    memory_fingerprint: str
    feedback_count: int
    feedback_memory_fingerprint: str
    pipeline_version: str

    def __post_init__(self):
        results = tuple(self.pipeline_results)
        if any(type(result) is not PipelineResult for result in results):
            raise ValueError('Expected ordered PipelineResult records')
        object.__setattr__(self, 'pipeline_results', results)
        if not isinstance(self.structural_summary, Mapping):
            raise ValueError('structural_summary must be a mapping')
        object.__setattr__(self, 'structural_summary', freeze(self.structural_summary))
        if type(self.experience_count) is not int or self.experience_count < 0:
            raise ValueError('experience_count must be a nonnegative integer')
        if self.experience_count != len(results):
            raise ValueError('Every completed pipeline event requires one experience')
        if not isinstance(self.memory_fingerprint, str) or not self.memory_fingerprint:
            raise ValueError('memory_fingerprint must be nonempty text')
        if type(self.feedback_count) is not int or self.feedback_count < 0:
            raise ValueError('feedback_count must be a nonnegative integer')
        if self.feedback_count != len(results):
            raise ValueError('Every completed pipeline event requires one feedback assessment')
        if not isinstance(self.feedback_memory_fingerprint, str) or not self.feedback_memory_fingerprint:
            raise ValueError('feedback_memory_fingerprint must be nonempty text')

    @property
    def episode_fingerprint(self):
        return fingerprint({
            'scenario_reference': self.scenario_reference,
            'seed': self.seed,
            'ordered_pipeline_fingerprints': [r.pipeline_fingerprint for r in self.pipeline_results],
            'initial_state_reference': self.initial_state_reference,
            'final_state_reference': self.final_state_reference,
            'experience_count': self.experience_count,
            'memory_fingerprint': self.memory_fingerprint,
            'feedback_count': self.feedback_count,
            'feedback_memory_fingerprint': self.feedback_memory_fingerprint,
            'pipeline_version': self.pipeline_version,
        })

    @property
    def final_state(self):
        return self.pipeline_results[-1].state_after if self.pipeline_results else None

    def to_dict(self):
        return {
            'scenario_reference': self.scenario_reference,
            'scenario_id': self.scenario_id,
            'seed': self.seed,
            'pipeline_results': [result.to_dict() for result in self.pipeline_results],
            'initial_state_reference': self.initial_state_reference,
            'final_state_reference': self.final_state_reference,
            'structural_summary': export(self.structural_summary),
            'experience_count': self.experience_count,
            'memory_fingerprint': self.memory_fingerprint,
            'feedback_count': self.feedback_count,
            'feedback_memory_fingerprint': self.feedback_memory_fingerprint,
            'pipeline_version': self.pipeline_version,
            'episode_fingerprint': self.episode_fingerprint,
        }
