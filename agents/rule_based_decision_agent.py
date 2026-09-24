"""Minimal deterministic observable-fact baseline for Milestone 8A."""
from core.actions import Action
from core.decision_context import AuthorizationStatus, DecisionContext
from core.decision_contracts import ProposedDecision
from core.operational_semantics import SemanticStatus
from core.planning_result import PlanningResult


RULE_BASELINE_VERSION = 'milestone8a-rule-baseline-v1'


class RuleBasedDecisionAgent:
    """Select ALLOW only for authenticated, authorized, supported-valid requests."""

    def decide(self, decision_context, planning_result):
        if type(decision_context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        if type(planning_result) is not PlanningResult:
            raise ValueError('Expected PlanningResult')
        if planning_result.context_fingerprint != decision_context.reference:
            raise ValueError('PlanningResult does not belong to DecisionContext')
        observation = decision_context.observation
        semantics = decision_context.operational_semantic_assessment
        routine = (
            observation['authentication_status'] is True and
            decision_context.authorization_status == AuthorizationStatus.AUTHORIZED and
            semantics.semantic_status == SemanticStatus.SUPPORTED_VALID)
        desired = Action.ALLOW if routine else Action.REQUEST_APPROVAL
        candidates = tuple(planning_result.candidates)
        if len(candidates) != 1 or candidates[0].action != desired:
            raise ValueError('Rule baseline plan does not match observable-fact decision rule')
        selected = candidates[0]
        reason = (
            'ALLOW: authenticated, explicitly authorized, and supported-valid routine request.'
            if selected.action == Action.ALLOW else
            'REQUEST_APPROVAL: authentication, authorization, or operational semantics is unresolved or invalid.')
        alternatives = ()
        return ProposedDecision(
            selected_action=selected.action,
            selected_candidate_reference=selected.reference,
            candidate_actions=candidates,
            primary_reason=reason,
            evidence_summary=(
                f'Authentication: {observation["authentication_status"]}.',
                f'Authorization: {decision_context.authorization_status.value}.',
                f'Operational semantics: {semantics.semantic_status.value}.'),
            trust_basis='Dynamic trust is not consumed by the rule baseline.',
            risk_basis='Risk score is not consumed by the rule baseline.',
            uncertainty=tuple(selected.unresolved_prerequisites),
            policy_basis=(f'Rule baseline {RULE_BASELINE_VERSION}.',),
            alternatives_considered=alternatives,
            context_reference=decision_context.reference,
            decision_policy_version=RULE_BASELINE_VERSION,
            planning_reference=planning_result.reference,
            planning_policy_version=planning_result.planning_policy_version)
