"""Observable-fact rule baseline planning artifact for shared governance."""
from core.actions import Action
from core.decision_context import AuthorizationStatus, DecisionContext
from core.decision_contracts import CandidateAction, export
from core.operational_semantics import SemanticStatus
from core.planning_result import PLANNING_VERSION, PlanningResult


class RuleBasedPlanningAgent:
    def plan(self, context):
        if type(context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        observation = context.observation
        semantics = context.operational_semantic_assessment
        routine = (
            observation['authentication_status'] is True and
            context.authorization_status == AuthorizationStatus.AUTHORIZED and
            semantics.semantic_status == SemanticStatus.SUPPORTED_VALID)
        action = Action.ALLOW if routine else Action.REQUEST_APPROVAL
        payload = {
            'source_id': context.source_id, 'target_id': context.target_id,
            'operation': observation['operation'],
            'requested_value': export(observation['requested_value']),
            'operating_mode': observation['contextual_features'].get('operating_mode'),
            'execution_ready': False,
        }
        if action == Action.REQUEST_APPROVAL:
            payload['purpose'] = 'DEFER_FOR_REVIEW'
        candidate = CandidateAction(
            action=action, payload=payload,
            rationale='Exact frozen observable-fact rule result.',
            safety_effect=('Permits governance review of the exact supported-valid request.'
                           if action == Action.ALLOW else
                           'Defers the request for review without authorizing it.'),
            operational_impact='Physical consequences remain subject to shared governance and execution.',
            reversibility='UNKNOWN: the rule baseline does not infer process reversibility.',
            requires_approval=action == Action.REQUEST_APPROVAL,
            policy_constraints=('Shared governance must validate the exact proposal.',),
            evidence_basis=(
                f'Authentication: {observation["authentication_status"]}.',
                f'Authorization: {context.authorization_status.value}.',
                f'Operational semantics: {semantics.semantic_status.value}.'),
            unresolved_prerequisites=(
                ('External approval remains unavailable.',)
                if action == Action.REQUEST_APPROVAL else
                ('Shared governance and execution validation remain required.',)),
            capability_reference=context.capabilities.reference,
            planning_policy_version=PLANNING_VERSION)
        exclusions = {
            other.value: 'Not selected by the frozen observable-fact rule.'
            for other in Action if other != action}
        return PlanningResult(
            candidates=(candidate,), context_fingerprint=context.reference,
            context_version=context.context_version,
            planning_policy_version=PLANNING_VERSION,
            unresolved_constraints=tuple(candidate.unresolved_prerequisites),
            exclusions=exclusions)
