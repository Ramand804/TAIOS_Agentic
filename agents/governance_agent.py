"""Independent deterministic governance of an exact proposal; never execution."""
from agents.base_agent import BaseAgent
from core.actions import Action
from core.autonomous_authority import AuthorityStatus
from core.decision_context import AuthorizationStatus, DecisionContext
from core.decision_contracts import (
    GovernanceDecision, GovernanceStatus, ProposedDecision, export,
)
from core.experiment import fingerprint
from core.planning_result import PlanningResult

GOVERNANCE_POLICY_VERSION = 'day4e-governance-v1'
CHECK_IDS = (
    'PROPOSAL_BOUND', 'PLANNER_CANDIDATE', 'AUTHORIZATION_VALID',
    'AUTHORITY_VALID', 'OPERATIONAL_VALIDITY', 'ACTION_PAYLOAD_COMPLETE',
    'REVIEW_REQUIREMENT', 'POLICY_CONFLICT', 'EXECUTION_PREREQUISITES',
)


def _set(checks, reasons, check_id, status, reason):
    checks[check_id] = status
    reasons[check_id] = reason


class GovernanceAgent(BaseAgent):
    @staticmethod
    def _veto(context, proposal, checks, reasons, violations, reason):
        return GovernanceDecision(
            status=GovernanceStatus.VETOED,
            proposed_action=proposal.selected_action,
            authorized_action=None,
            authorized_payload=None,
            policy_checks=checks,
            check_reasons=reasons,
            violations=tuple(violations),
            reason=reason,
            context_reference=context.reference,
            proposal_reference=proposal.reference,
            authorization_reference=None,
            governance_policy_version=GOVERNANCE_POLICY_VERSION,
        )

    def review(self, decision_context, planning_result, proposed_decision):
        if type(decision_context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        if type(planning_result) is not PlanningResult:
            raise ValueError('Expected PlanningResult')
        if type(proposed_decision) is not ProposedDecision:
            raise ValueError('Expected ProposedDecision')

        context, plan, proposal = decision_context, planning_result, proposed_decision
        checks = {check_id: 'UNKNOWN' for check_id in CHECK_IDS}
        reasons = {check_id: 'Not evaluated because an earlier integrity prerequisite failed.'
                   for check_id in CHECK_IDS}
        violations = []

        binding_failures = []
        if plan.context_fingerprint != context.reference or plan.context_version != context.context_version:
            binding_failures.append('PlanningResult context binding mismatch.')
        if proposal.context_reference != context.reference:
            binding_failures.append('ProposedDecision context binding mismatch.')
        if proposal.planning_reference != plan.reference:
            binding_failures.append('ProposedDecision planning reference mismatch.')
        if proposal.planning_policy_version != plan.planning_policy_version:
            binding_failures.append('ProposedDecision planning version mismatch.')
        plan_map = {(candidate.action, candidate.reference): candidate for candidate in plan.candidates}
        proposal_map = {(candidate.action, candidate.reference): candidate for candidate in proposal.candidate_actions}
        if proposal_map != plan_map:
            binding_failures.append('ProposedDecision candidate set differs from PlanningResult.')
        if binding_failures:
            _set(checks, reasons, 'PROPOSAL_BOUND', 'FAIL', ' '.join(binding_failures))
            _set(checks, reasons, 'PLANNER_CANDIDATE', 'FAIL',
                 'Candidate membership cannot be trusted when the inference chain is mismatched.')
            violations.extend(binding_failures)
            return self._veto(
                context, proposal, checks, reasons, violations,
                'VETOED: exact context/plan/proposal binding failed; governance does not repair proposals.')

        _set(checks, reasons, 'PROPOSAL_BOUND', 'PASS',
             'Context, planning reference/version and exact candidate set are bound.')
        selected = None
        if proposal.selected_action is not None:
            selected = plan_map.get((proposal.selected_action, proposal.selected_candidate_reference))
        if proposal.selected_action is None:
            if plan.candidates:
                _set(checks, reasons, 'PLANNER_CANDIDATE', 'FAIL',
                     'No proposal was selected despite a nonempty plan.')
                violations.append('Missing selected proposal for nonempty plan.')
            else:
                _set(checks, reasons, 'PLANNER_CANDIDATE', 'PASS',
                     'The empty proposal exactly matches the empty plan.')
            return self._veto(
                context, proposal, checks, reasons, violations,
                'VETOED: there is no proposed action to authorize; no fallback action is injected.')
        if selected is None:
            _set(checks, reasons, 'PLANNER_CANDIDATE', 'FAIL',
                 'Selected action/reference is not an exact PlanningResult candidate.')
            violations.append('Proposal is not a planner candidate.')
            return self._veto(
                context, proposal, checks, reasons, violations,
                'VETOED: proposed action is not an exact planner candidate.')
        if selected.capability_reference != context.capabilities.reference:
            _set(checks, reasons, 'PLANNER_CANDIDATE', 'FAIL',
                 'Selected candidate capability reference differs from DecisionContext.')
            violations.append('Candidate capability binding mismatch.')
            return self._veto(
                context, proposal, checks, reasons, violations,
                'VETOED: candidate capability binding failed.')
        _set(checks, reasons, 'PLANNER_CANDIDATE', 'PASS',
             'Proposed action/reference and payload are the exact planner candidate.')

        action = selected.action
        validity = context.capabilities.operational_validity
        authority = context.autonomous_authority_assessment
        requires_request_authorization = action in (Action.ALLOW, Action.MONITOR, Action.LIMIT)
        if not requires_request_authorization:
            _set(checks, reasons, 'AUTHORIZATION_VALID', 'PASS',
                 f'{action.value} does not authorize the underlying industrial request.')
        elif context.authorization_status == AuthorizationStatus.AUTHORIZED:
            _set(checks, reasons, 'AUTHORIZATION_VALID', 'PASS',
                 'The bound AuthorizationAssessment is AUTHORIZED.')
        elif context.authorization_status == AuthorizationStatus.UNKNOWN:
            _set(checks, reasons, 'AUTHORIZATION_VALID', 'UNKNOWN',
                 'Authorization is UNKNOWN and cannot permit the underlying operation.')
        else:
            _set(checks, reasons, 'AUTHORIZATION_VALID', 'FAIL',
                 'Authorization is UNAUTHORIZED.')
            violations.append('Proposed action requires authorization that is explicitly denied.')

        if authority is None:
            _set(checks, reasons, 'AUTHORITY_VALID', 'UNKNOWN',
                 'No AutonomousAuthorityAssessment is bound.')
        else:
            authority_status = authority.status_for(action)
            if authority_status == AuthorityStatus.PERMITTED:
                _set(checks, reasons, 'AUTHORITY_VALID', 'PASS',
                     f'{action.value} authority is explicitly PERMITTED.')
            elif authority_status == AuthorityStatus.NOT_PERMITTED:
                _set(checks, reasons, 'AUTHORITY_VALID', 'FAIL',
                     f'{action.value} authority is NOT_PERMITTED.')
                violations.append(f'Autonomous authority prohibits {action.value}.')
            else:
                _set(checks, reasons, 'AUTHORITY_VALID', 'UNKNOWN',
                     f'{action.value} authority is UNKNOWN.')

        if action in (Action.ALLOW, Action.MONITOR):
            if validity.status == 'WITHIN_LIMIT':
                _set(checks, reasons, 'OPERATIONAL_VALIDITY', 'PASS',
                     f'Request is within the bound {validity.operating_mode} operational range.')
            elif validity.status == 'OUTSIDE_LIMIT':
                _set(checks, reasons, 'OPERATIONAL_VALIDITY', 'FAIL',
                     'A permissive action cannot govern an outside-limit request.')
                violations.append('Permissive proposal violates the bound operational range.')
            else:
                _set(checks, reasons, 'OPERATIONAL_VALIDITY', 'UNKNOWN',
                     'Current operation/mode validity is unknown.')
        elif action == Action.LIMIT:
            if validity.status == 'OUTSIDE_LIMIT' and validity.check is not None:
                _set(checks, reasons, 'OPERATIONAL_VALIDITY', 'PASS',
                     'The bound context establishes an outside-limit request and current range.')
            else:
                status = 'UNKNOWN' if validity.status == 'UNKNOWN' else 'FAIL'
                _set(checks, reasons, 'OPERATIONAL_VALIDITY', status,
                     'LIMIT requires an established outside-limit request and current range.')
                if status == 'FAIL': violations.append('LIMIT has no applicable operational violation.')
        else:
            _set(checks, reasons, 'OPERATIONAL_VALIDITY', 'PASS',
                 f'{action.value} does not assert that the underlying request is operationally valid.')

        payload = selected.payload
        base_fields = ('source_id', 'target_id', 'operation', 'requested_value', 'execution_ready')
        base_complete = all(name in payload for name in base_fields)
        if action in (Action.ALLOW, Action.MONITOR):
            monitor_complete = action != Action.MONITOR or payload.get('monitoring_mode') == 'LOGICAL_ONLY'
            complete = base_complete and monitor_complete
            _set(checks, reasons, 'ACTION_PAYLOAD_COMPLETE', 'PASS' if complete else 'FAIL',
                 'Exact request payload is complete; execution support remains a later-stage check.' if complete else
                 'Permissive candidate payload is incomplete or changes monitoring semantics.')
            if not complete: violations.append('Proposed payload is incomplete.')
        elif action == Action.REQUEST_APPROVAL:
            complete = base_complete and payload.get('purpose') == 'DEFER_FOR_REVIEW'
            _set(checks, reasons, 'ACTION_PAYLOAD_COMPLETE', 'PASS' if complete else 'FAIL',
                 'Payload explicitly routes the exact request for review.' if complete else
                 'Review proposal lacks an exact deferral payload.')
            if not complete: violations.append('Review payload is incomplete.')
        elif action == Action.LIMIT:
            replacement = payload.get('replacement_value')
            check = validity.check
            complete = (base_complete and check is not None and replacement is not None and
                        payload.get('allowed_min') == check.minimum and
                        payload.get('allowed_max') == check.maximum and
                        not isinstance(replacement, bool) and isinstance(replacement, (int, float)) and
                        check.minimum <= replacement <= check.maximum)
            _set(checks, reasons, 'ACTION_PAYLOAD_COMPLETE', 'PASS' if complete else 'UNKNOWN',
                 'Exact replacement is present and lies within the bound current range.' if complete else
                 'LIMIT has no reviewed exact replacement within the bound current range.')
        else:
            _set(checks, reasons, 'ACTION_PAYLOAD_COMPLETE', 'FAIL',
                 f'No reviewed executable payload semantics exist for {action.value}.')
            violations.append(f'{action.value} payload semantics are unsupported.')

        if action == Action.REQUEST_APPROVAL:
            _set(checks, reasons, 'REVIEW_REQUIREMENT', 'UNKNOWN',
                 'External human approval is required and no approval response exists.')
        elif selected.requires_approval:
            _set(checks, reasons, 'REVIEW_REQUIREMENT', 'UNKNOWN',
                 'Candidate explicitly requires approval; no approval response exists.')
        else:
            _set(checks, reasons, 'REVIEW_REQUIREMENT', 'PASS',
                 'The candidate has no unresolved human-approval prerequisite.')

        if action in (Action.BLOCK, Action.ISOLATE):
            _set(checks, reasons, 'POLICY_CONFLICT', 'FAIL',
                 f'Current authority policy explicitly prohibits {action.value}.')
            violations.append(f'Current policy prohibits {action.value}.')
        elif checks['AUTHORITY_VALID'] == 'PASS':
            _set(checks, reasons, 'POLICY_CONFLICT', 'PASS',
                 'No explicit action-authority conflict remains.')
        else:
            _set(checks, reasons, 'POLICY_CONFLICT', 'UNKNOWN',
                 'Policy clearance cannot be established without permitted authority.')

        if action in (Action.ALLOW, Action.MONITOR):
            _set(checks, reasons, 'EXECUTION_PREREQUISITES', 'PASS',
                 'Governance can authorize the exact payload artifact; executor capability and current-state revalidation remain mandatory later checks.')
        elif action == Action.REQUEST_APPROVAL:
            _set(checks, reasons, 'EXECUTION_PREREQUISITES', 'UNKNOWN',
                 'No external approval workflow or physical hold is implemented.')
        elif action == Action.LIMIT and checks['ACTION_PAYLOAD_COMPLETE'] == 'PASS':
            _set(checks, reasons, 'EXECUTION_PREREQUISITES', 'PASS',
                 'Exact bounded payload is governance-complete; executor support remains a later check.')
        elif action == Action.LIMIT:
            _set(checks, reasons, 'EXECUTION_PREREQUISITES', 'UNKNOWN',
                 'LIMIT remains pending an exact reviewed transformation and approval.')
        else:
            _set(checks, reasons, 'EXECUTION_PREREQUISITES', 'FAIL',
                 f'No executable {action.value} capability/envelope is established.')
            violations.append(f'Execution prerequisites for {action.value} are absent.')

        score_note = (f'Trust estimate {context.trust_assessment.composite_trust:.12g}; risk estimate '
                      f'{context.risk_assessment.risk_score} with coverage '
                      f'{context.risk_assessment.coverage:.12g}; no score threshold applied.')
        if action == Action.REQUEST_APPROVAL:
            status = GovernanceStatus.APPROVAL_REQUIRED
            reason = 'APPROVAL_REQUIRED: proposal is a review request; no external approval is fabricated. ' + score_note
        elif violations or any(checks[key] == 'FAIL' for key in CHECK_IDS):
            status = GovernanceStatus.VETOED
            reason = 'VETOED: one or more mandatory governance constraints failed. ' + score_note
        elif selected.requires_approval or any(checks[key] == 'UNKNOWN' for key in CHECK_IDS):
            status = GovernanceStatus.APPROVAL_REQUIRED
            reason = 'APPROVAL_REQUIRED: mandatory information or human approval remains unresolved. ' + score_note
        else:
            status = GovernanceStatus.APPROVED
            reason = 'APPROVED: every mandatory check passes for the exact proposed context and payload. ' + score_note

        if status != GovernanceStatus.APPROVED:
            return GovernanceDecision(
                status=status,
                proposed_action=action,
                authorized_action=None,
                authorized_payload=None,
                policy_checks=checks,
                check_reasons=reasons,
                violations=tuple(dict.fromkeys(violations)),
                reason=reason,
                context_reference=context.reference,
                proposal_reference=proposal.reference,
                authorization_reference=None,
                governance_policy_version=GOVERNANCE_POLICY_VERSION,
            )

        authorization_reference = fingerprint({
            'context_reference': context.reference,
            'planning_reference': plan.reference,
            'proposal_reference': proposal.reference,
            'action': action.value,
            'payload': export(selected.payload),
            'checks': checks,
            'governance_policy_version': GOVERNANCE_POLICY_VERSION,
        })
        return GovernanceDecision(
            status=status,
            proposed_action=action,
            authorized_action=action,
            authorized_payload=selected.payload,
            policy_checks=checks,
            check_reasons=reasons,
            violations=(),
            reason=reason,
            context_reference=context.reference,
            proposal_reference=proposal.reference,
            authorization_reference=authorization_reference,
            governance_policy_version=GOVERNANCE_POLICY_VERSION,
        )
