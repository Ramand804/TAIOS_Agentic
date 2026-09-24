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
    authority_assessment: object
    decision_context: object
    planning_result: object
    proposed_decision: object
    governance_decision: object
    execution_result: object
    input_state_reference: str
    state_before: IndustrialState
    state_after: IndustrialState
    regime_transition_applied: bool
    pipeline_version: str

    def __post_init__(self):
        object.__setattr__(self, 'observable_input', freeze(self.observable_input))
        if type(self.state_before) is not IndustrialState or type(self.state_after) is not IndustrialState:
            raise ValueError('Pipeline states must be IndustrialState')
        if type(self.regime_transition_applied) is not bool:
            raise ValueError('regime_transition_applied must be bool')
        if self.decision_context.observation != self.observable_input:
            raise ValueError('Context observation is not the pipeline observation')
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

    @property
    def pipeline_fingerprint(self):
        return fingerprint({
            'event_reference': self.event_reference,
            'context_reference': self.decision_context.reference,
            'planning_reference': self.planning_result.reference,
            'proposal_reference': self.proposed_decision.reference,
            'governance_reference': self.governance_decision.reference,
            'execution_reference': self.execution_result.reference,
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
            'authority_assessment': self.authority_assessment.to_dict(),
            'decision_context': self.decision_context.to_dict(),
            'planning_result': self.planning_result.to_dict(),
            'proposed_decision': self.proposed_decision.to_dict(),
            'governance_decision': self.governance_decision.to_dict(),
            'execution_result': self.execution_result.to_dict(),
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
    pipeline_version: str

    def __post_init__(self):
        results = tuple(self.pipeline_results)
        if any(type(result) is not PipelineResult for result in results):
            raise ValueError('Expected ordered PipelineResult records')
        object.__setattr__(self, 'pipeline_results', results)
        if not isinstance(self.structural_summary, Mapping):
            raise ValueError('structural_summary must be a mapping')
        object.__setattr__(self, 'structural_summary', freeze(self.structural_summary))

    @property
    def episode_fingerprint(self):
        return fingerprint({
            'scenario_reference': self.scenario_reference,
            'seed': self.seed,
            'ordered_pipeline_fingerprints': [r.pipeline_fingerprint for r in self.pipeline_results],
            'initial_state_reference': self.initial_state_reference,
            'final_state_reference': self.final_state_reference,
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
            'pipeline_version': self.pipeline_version,
            'episode_fingerprint': self.episode_fingerprint,
        }
