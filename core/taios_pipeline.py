"""Minimal deterministic orchestration of existing TAIOS components."""
from collections import Counter, defaultdict

from agents.decision_agent import DecisionAgent
from agents.execution_agent import ExecutionAgent, clone_state
from agents.governance_agent import GovernanceAgent
from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.event_manager import EventManager
from core.experiment import fingerprint
from core.pipeline_result import (
    EpisodeResult, PipelineFailure, PipelineProcessingError, PipelineResult,
)
from core.runtime_inputs import runtime_observation
from environment.industrial_environment import IndustrialState
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context
from intelligence.operational_semantic_model import OperationalSemanticModel
from intelligence.threat_evidence_model import ThreatEvidenceModel

PIPELINE_VERSION = 'milestone6c-pipeline-v1'


class TAIOSPipeline:
    def __init__(self, *, event_manager=None, trust_agent=None, risk_agent=None,
                 authorization_engine=None, authority_engine=None, planning_agent=None,
                 decision_agent=None, governance_agent=None, execution_agent=None,
                 operational_semantic_model=None, threat_evidence_model=None):
        self.event_manager = event_manager or EventManager()
        self.trust_agent = trust_agent or TrustAgent()
        self.risk_agent = risk_agent or RiskAgent()
        self.authorization_engine = authorization_engine or AuthorizationEngine()
        self.authority_engine = authority_engine or AutonomousAuthorityEngine()
        self.planning_agent = planning_agent or PlanningAgent()
        self.decision_agent = decision_agent or DecisionAgent()
        self.governance_agent = governance_agent or GovernanceAgent()
        self.execution_agent = execution_agent or ExecutionAgent()
        self.operational_semantic_model = operational_semantic_model or OperationalSemanticModel()
        self.threat_evidence_model = threat_evidence_model or ThreatEvidenceModel()
        self._entity_observations = defaultdict(int)
        self._processed_events = {}

    def reset(self):
        self.trust_agent.reset()
        self.execution_agent._restore({})
        self.threat_evidence_model.reset()
        self._entity_observations.clear()
        self._processed_events.clear()

    @staticmethod
    def _failure(stage, exc, event, state):
        observation_reference = None
        try:
            observation_reference = fingerprint(runtime_observation(event))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        failure = PipelineFailure(
            stage=stage, error_type=type(exc).__name__, reason=str(exc),
            event_reference=observation_reference,
            state_reference=fingerprint(state.to_dict()),
            pipeline_version=PIPELINE_VERSION)
        raise PipelineProcessingError(failure) from exc

    @staticmethod
    def _synchronize_regime(state, observation):
        synchronized = clone_state(state)
        before = synchronized.state_version
        context = observation['contextual_features']
        if 'production_state' in context:
            synchronized.set_production_state(context['production_state'])
        if 'operating_mode' in context:
            synchronized.set_operating_mode(context['operating_mode'])
        return synchronized, synchronized.state_version != before

    def process_event(self, event, state):
        if type(state) is not IndustrialState:
            raise ValueError('Expected IndustrialState')
        input_state_reference = fingerprint(state.to_dict())
        event_key = getattr(event, 'event_id', None)
        prior = self._processed_events.get(event_key)
        if (prior is not None and fingerprint(runtime_observation(event)) == prior.event_reference and
                input_state_reference == fingerprint(prior.state_after.to_dict())):
            replay = self.execution_agent.execute(
                prior.decision_context, prior.planning_result, prior.proposed_decision,
                prior.governance_decision, state)
            return PipelineResult(
                event_id=event.event_id, sequence_number=event.sequence_number,
                event_reference=prior.event_reference,
                observable_input=prior.observable_input,
                trust_assessment=prior.trust_assessment,
                risk_assessment=prior.risk_assessment,
                authorization_assessment=prior.authorization_assessment,
                operational_semantic_assessment=prior.operational_semantic_assessment,
                threat_assessment=prior.threat_assessment,
                authority_assessment=prior.authority_assessment,
                decision_context=prior.decision_context,
                planning_result=prior.planning_result,
                proposed_decision=prior.proposed_decision,
                governance_decision=prior.governance_decision,
                execution_result=replay, input_state_reference=input_state_reference,
                state_before=clone_state(state),
                state_after=clone_state(replay.resulting_state),
                regime_transition_applied=False, pipeline_version=PIPELINE_VERSION)
        trust_checkpoint = self.trust_agent._checkpoint()
        counts_checkpoint = dict(self._entity_observations)
        execution_checkpoint = self.execution_agent._checkpoint()
        threat_checkpoint = self.threat_evidence_model._checkpoint()
        stage = 'event_validation'
        try:
            self.event_manager.validate((event,))
            stage = 'observable_input'
            observation = runtime_observation(event)
            state_before, regime_transition = self._synchronize_regime(state, observation)

            stage = 'operational_semantics'
            semantics = self.operational_semantic_model.assess(observation)

            stage = 'authorization_assessment'
            authorization = self.authorization_engine.assess(observation)
            stage = 'threat_evidence'
            threat = self.threat_evidence_model.assess(
                observation, semantics, authorization)
            source = observation['source_id']
            self._entity_observations[source] += 1
            observation_number = self._entity_observations[source]
            stage = 'trust_assessment'
            trust = self.trust_agent.assess(
                observation, delivery_token=f'pipeline-{source}-{observation_number}',
                observation_number=observation_number)
            stage = 'risk_assessment'
            risk = self.risk_agent.assess(
                observation, trust,
                expected_trust_state_version=trust.trust_state_version,
                threat_assessment=threat)
            stage = 'decision_context'
            base_context = build_decision_context(
                observation, trust, risk, authorization,
                permission_policy=self.authorization_engine.policy,
                operational_semantic_assessment=semantics,
                industrial_state=state_before)
            stage = 'authority_assessment'
            authority = self.authority_engine.assess(base_context)
            stage = 'final_decision_context'
            context = build_decision_context(
                observation, trust, risk, authorization,
                permission_policy=self.authorization_engine.policy,
                autonomous_authority_assessment=authority,
                authority_policy=self.authority_engine.policy,
                operational_semantic_assessment=semantics,
                industrial_state=state_before)
            stage = 'planning'
            plan = self.planning_agent.plan(context)
            stage = 'decision'
            proposal = self.decision_agent.decide(context, plan)
            stage = 'governance'
            governance = self.governance_agent.review(context, plan, proposal)
            stage = 'execution'
            execution = self.execution_agent.execute(
                context, plan, proposal, governance, state_before)
            state_after = clone_state(execution.resulting_state)
            result = PipelineResult(
                event_id=event.event_id, sequence_number=event.sequence_number,
                event_reference=fingerprint(observation), observable_input=observation,
                trust_assessment=trust, risk_assessment=risk,
                authorization_assessment=authorization,
                operational_semantic_assessment=semantics,
                threat_assessment=threat,
                authority_assessment=authority, decision_context=context,
                planning_result=plan, proposed_decision=proposal,
                governance_decision=governance, execution_result=execution,
                input_state_reference=input_state_reference,
                state_before=clone_state(state_before), state_after=state_after,
                regime_transition_applied=regime_transition,
                pipeline_version=PIPELINE_VERSION)
            self._processed_events[event_key] = result
            return result
        except PipelineProcessingError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            self.trust_agent._restore(trust_checkpoint)
            self._entity_observations = defaultdict(int, counts_checkpoint)
            self.execution_agent._restore(execution_checkpoint)
            self.threat_evidence_model._restore(threat_checkpoint)
            self._failure(stage, exc, event, state)

    def run_episode(self, events, initial_state=None, *, scenario_reference=None, seed=None):
        self.reset()
        events = tuple(events)
        state = clone_state(initial_state or IndustrialState())
        initial_reference = fingerprint(state.to_dict())
        results = []
        for event in events:
            result = self.process_event(event, state)
            results.append(result)
            state = clone_state(result.state_after)
        scenario_id = events[0].scenario_id if events else 'EMPTY'
        if events and any(event.scenario_id != scenario_id for event in events):
            raise ValueError('Episode events must share one scenario_id')
        proposals = Counter(
            result.proposed_decision.selected_action.value for result in results)
        governance = Counter(result.governance_decision.status.value for result in results)
        execution = Counter(result.execution_result.execution_status.value for result in results)
        scenario_reference = scenario_reference or (
            events[0].experiment_id if events and events[0].experiment_id else
            fingerprint({'scenario_id': scenario_id,
                         'event_references': [result.event_reference for result in results]}))
        return EpisodeResult(
            scenario_reference=scenario_reference, scenario_id=scenario_id, seed=seed,
            pipeline_results=tuple(results), initial_state_reference=initial_reference,
            final_state_reference=fingerprint(state.to_dict()),
            structural_summary={
                'total_events': len(results),
                'proposals': dict(sorted(proposals.items())),
                'governance_statuses': dict(sorted(governance.items())),
                'execution_statuses': dict(sorted(execution.items())),
                'state_mutations': sum(r.execution_result.mutation_applied for r in results),
                'regime_transitions': sum(r.regime_transition_applied for r in results),
            }, pipeline_version=PIPELINE_VERSION)
