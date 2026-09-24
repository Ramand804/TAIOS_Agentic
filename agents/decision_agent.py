"""Deterministic proposal selection from an already validated candidate set."""
from agents.base_agent import BaseAgent
from core.actions import Action
from core.autonomous_authority import AuthorityStatus
from core.decision_context import AuthorizationStatus, DecisionContext
from core.decision_contracts import ProposedDecision
from core.planning_result import PlanningResult

DECISION_POLICY_VERSION = 'day4d-decision-v1'


class DecisionAgent(BaseAgent):
    @staticmethod
    def _canonical_candidates(candidates):
        candidates = tuple(candidates)
        if len({candidate.action for candidate in candidates}) != len(candidates):
            raise ValueError('Decision candidates must have unique actions')
        return tuple(sorted(candidates, key=lambda candidate: tuple(Action).index(candidate.action)))

    @staticmethod
    def _select(candidates, context):
        candidates = DecisionAgent._canonical_candidates(candidates)
        by_action = {candidate.action: candidate for candidate in candidates}
        if not candidates:
            return None, 'No admissible candidates were supplied; no action is proposed.'
        if len(candidates) == 1:
            candidate = candidates[0]
            return candidate, f'{candidate.action.value} is the only admissible candidate.'

        actions = set(by_action)
        authority = context.autonomous_authority_assessment
        if actions == {Action.ALLOW, Action.MONITOR}:
            routine = (
                context.authorization_status == AuthorizationStatus.AUTHORIZED and
                context.capabilities.operational_validity.status == 'WITHIN_LIMIT' and
                authority is not None and
                authority.status_for(Action.ALLOW) == AuthorityStatus.PERMITTED and
                not by_action[Action.ALLOW].requires_approval
            )
            if not routine:
                raise ValueError('ALLOW/MONITOR set lacks the bound routine-autonomy facts')
            return by_action[Action.ALLOW], (
                'ALLOW is proposed for the exact authorized, current-mode-conforming routine request; '
                'MONITOR remains an unselected logical alternative.')

        if actions == {Action.LIMIT, Action.REQUEST_APPROVAL}:
            limit = by_action[Action.LIMIT]
            check = context.capabilities.operational_validity.check
            established_violation = (
                context.capabilities.operational_validity.status == 'OUTSIDE_LIMIT' and
                check is not None and authority is not None and
                authority.status_for(Action.LIMIT) == AuthorityStatus.PERMITTED
            )
            if not established_violation:
                raise ValueError('LIMIT/review set lacks a bound operational violation')
            if limit.requires_approval or limit.payload.get('replacement_value') is None:
                return by_action[Action.REQUEST_APPROVAL], (
                    'REQUEST_APPROVAL is proposed because LIMIT remains a range-only alternative '
                    'requiring approval and an exact reviewed transformation; no replacement value is inferred.')
            return limit, (
                'LIMIT is proposed for the established current-mode range violation using the exact '
                'planner payload; no replacement value is inferred by DecisionAgent.')

        if Action.REQUEST_APPROVAL in by_action and any(
                candidate.requires_approval for candidate in candidates if candidate.action != Action.REQUEST_APPROVAL):
            return by_action[Action.REQUEST_APPROVAL], (
                'REQUEST_APPROVAL is proposed because another candidate retains an explicit human-approval prerequisite.')
        raise ValueError('No reviewed semantic decision rule covers this candidate set')

    def decide(self, decision_context, planning_result):
        if type(decision_context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        if type(planning_result) is not PlanningResult:
            raise ValueError('Expected PlanningResult')
        if planning_result.context_fingerprint != decision_context.reference:
            raise ValueError('PlanningResult does not belong to DecisionContext')
        if planning_result.context_version != decision_context.context_version:
            raise ValueError('PlanningResult context version mismatch')

        candidates = self._canonical_candidates(planning_result.candidates)
        selected, reason = self._select(candidates, decision_context)
        trust = decision_context.trust_assessment
        risk = decision_context.risk_assessment
        authority = decision_context.autonomous_authority_assessment
        evidence = (
            f'Authorization: {decision_context.authorization_status.value}.',
            f'Operational validity: {decision_context.capabilities.operational_validity.status}; '
            f'mode: {decision_context.capabilities.operational_validity.operating_mode or "UNKNOWN"}.',
            f'Trust estimate: {trust.composite_trust:.12g}; direct evidence: ' +
                '; '.join(f'{name}={"/".join(signs)}' for name, signs in trust.evidence_coverage.items()),
            f'Risk estimate: {risk.risk_score}; weighted evidence coverage: {risk.coverage:.12g}; '
            'not an attack probability or calibrated severity.',
            f'Planning reference: {planning_result.reference}; policy: {planning_result.planning_policy_version}.',
        )
        if authority is not None:
            evidence += (f'Authority policy: {authority.authority_policy_version}; '
                         f'fingerprint: {authority.authority_policy_fingerprint}.',)

        trust_basis = (f'Composite trust estimate {trust.composite_trust:.12g}, state version '
                       f'{trust.trust_state_version}; no numeric trust category or decision threshold applied.')
        risk_basis = (f'Risk estimate {risk.risk_score} with weighted evidence coverage '
                      f'{risk.coverage:.12g}; no numeric risk category or action threshold applied.')
        if selected is None:
            uncertainty = tuple(planning_result.unresolved_constraints)
            policy_basis = (f'Planning policy {planning_result.planning_policy_version}.',
                            'No candidate was available; ALLOW was not injected.')
            alternatives = ()
            selected_action = selected_reference = None
        else:
            uncertainty = tuple(dict.fromkeys(
                tuple(planning_result.unresolved_constraints) + tuple(selected.unresolved_prerequisites)))
            policy_basis = tuple(dict.fromkeys(
                (f'Planning policy {planning_result.planning_policy_version}.',
                 f'Decision policy {DECISION_POLICY_VERSION}.') + tuple(selected.policy_constraints)))
            alternatives = tuple(
                f'{candidate.action.value}: {candidate.rationale}'
                for candidate in candidates if candidate.reference != selected.reference)
            selected_action, selected_reference = selected.action, selected.reference
            evidence += tuple(selected.evidence_basis)

        return ProposedDecision(
            selected_action=selected_action,
            selected_candidate_reference=selected_reference,
            candidate_actions=candidates,
            primary_reason=reason,
            evidence_summary=evidence,
            trust_basis=trust_basis,
            risk_basis=risk_basis,
            uncertainty=uncertainty,
            policy_basis=policy_basis,
            alternatives_considered=alternatives,
            context_reference=decision_context.reference,
            decision_policy_version=DECISION_POLICY_VERSION,
            planning_reference=planning_result.reference,
            planning_policy_version=planning_result.planning_policy_version,
        )
