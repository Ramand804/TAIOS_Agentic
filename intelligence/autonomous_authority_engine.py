"""Deterministic per-action autonomous-authority assessment."""
from core.actions import Action
from core.autonomous_authority import (
    AutonomousAuthorityAssessment, AuthorityPolicy, AuthorityStatus,
)
from core.decision_context import AuthorizationStatus, DecisionContext


class AutonomousAuthorityEngine:
    def __init__(self, policy=None):
        self.policy = AuthorityPolicy.load() if policy is None else policy
        if type(self.policy) is not AuthorityPolicy:
            raise ValueError('Expected AuthorityPolicy')

    @staticmethod
    def _routine(context):
        coverage = context.trust_assessment.evidence_coverage
        required = ('IDENTITY', 'DEVICE', 'BEHAVIOR')
        direct_positive = all('POSITIVE' in coverage[name] and 'NEGATIVE' not in coverage[name]
                              for name in required)
        return (context.authorization_status == AuthorizationStatus.AUTHORIZED and
                context.capabilities.operational_validity.status == 'WITHIN_LIMIT' and
                direct_positive)

    @classmethod
    def _matches(cls, condition, context):
        routine = cls._routine(context)
        validity = context.capabilities.operational_validity.status
        if condition == 'ALWAYS':
            return True
        if condition == 'ROUTINE_AUTHORIZED_VALID':
            return routine
        if condition == 'NOT_ROUTINE_AUTHORIZED_VALID':
            return not routine
        if condition == 'AUTHORIZED_OUTSIDE_LIMIT':
            return context.authorization_status == AuthorizationStatus.AUTHORIZED and validity == 'OUTSIDE_LIMIT'
        if condition == 'WITHIN_LIMIT':
            return validity == 'WITHIN_LIMIT'
        if condition == 'UNRESOLVED_OR_OUTSIDE':
            return context.authorization_status != AuthorizationStatus.AUTHORIZED or validity != 'WITHIN_LIMIT'
        raise ValueError('Unsupported authority condition')

    def assess(self, decision_context):
        if type(decision_context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        if decision_context.authorization_assessment is None:
            raise ValueError('Explicit AuthorizationAssessment is required')
        supported = set(decision_context.capabilities.supported_actions)
        statuses, matched, reasons = {}, {}, {}
        for action in Action:
            rules = tuple(rule for rule in self.policy.rules
                          if rule.action == action and self._matches(rule.condition, decision_context))
            ids = tuple(rule.rule_id for rule in rules)
            action_reasons = [f'{rule.rule_id}: {rule.rationale}' for rule in rules]
            if action not in supported:
                status = AuthorityStatus.NOT_PERMITTED
                action_reasons.insert(0, 'CAPABILITY_UNAVAILABLE: logical action capability is not established.')
            elif any(rule.status == AuthorityStatus.NOT_PERMITTED for rule in rules):
                status = AuthorityStatus.NOT_PERMITTED
                action_reasons.insert(0, 'RESTRICTIVE_PRECEDENCE: a matching restriction overrides permissions.')
            elif any(rule.status == AuthorityStatus.PERMITTED for rule in rules):
                status = AuthorityStatus.PERMITTED
                action_reasons.insert(0, 'EXPLICIT_AUTHORITY: a matching policy permits consideration, not selection or execution.')
            else:
                status = AuthorityStatus.UNKNOWN
                action_reasons.append('NO_MATCHING_RULE: autonomous authority is unresolved.')
            statuses[action.value] = status.value
            matched[action.value] = ids
            reasons[action.value] = tuple(action_reasons)
        unresolved = []
        if decision_context.authorization_status != AuthorizationStatus.AUTHORIZED:
            unresolved.append(f'Operation authorization is {decision_context.authorization_status.value}.')
        if decision_context.capabilities.operational_validity.status == 'UNKNOWN':
            unresolved.append('Operation/current-mode semantics are unknown.')
        if decision_context.risk_assessment.coverage < 1:
            unresolved.append('Risk evidence coverage is incomplete; it is not interpreted as confidence.')
        coverage = decision_context.trust_assessment.evidence_coverage
        for dimension in ('HISTORY', 'CONTEXT'):
            if tuple(coverage[dimension]) == ('INSUFFICIENT',):
                unresolved.append(f'Direct {dimension} trust evidence is insufficient.')
        return AutonomousAuthorityAssessment(
            source_id=decision_context.source_id,
            identity_id=decision_context.observation['identity_id'],
            target_id=decision_context.target_id,
            operation=decision_context.observation['operation'],
            authorization_status=decision_context.authorization_status,
            operational_validity=decision_context.capabilities.operational_validity.status,
            action_authority=statuses,
            matched_policy_ids=matched,
            unresolved_requirements=tuple(unresolved),
            reasons=reasons,
            authority_policy_version=self.policy.policy_version,
            authority_policy_fingerprint=self.policy.reference,
            context_input_reference=decision_context.authority_input_reference,
        )
