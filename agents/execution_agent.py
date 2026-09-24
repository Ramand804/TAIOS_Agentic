"""Fail-closed deterministic application of an exact governance authorization."""
from agents.base_agent import BaseAgent
from agents.governance_agent import (
    GOVERNANCE_POLICY_VERSION, governance_authorization_reference,
)
from core.actions import Action
from core.decision_context import DecisionContext
from core.decision_contracts import (
    ExecutionResult, ExecutionStatus, GovernanceDecision, GovernanceStatus,
    ProposedDecision, export,
)
from core.experiment import fingerprint
from core.planning_result import PlanningResult
from environment.industrial_environment import IndustrialState

EXECUTION_POLICY_VERSION = 'day4f-execution-v1'


def clone_state(state):
    if type(state) is not IndustrialState:
        raise ValueError('Expected IndustrialState')
    return IndustrialState(
        production_state=state.production_state,
        operating_mode=state.operating_mode,
        maintenance_mode=state.maintenance_mode,
        emergency_state=state.emergency_state,
        asset_states=dict(state.asset_states),
        state_version=state.state_version,
    )


class ExecutionAgent(BaseAgent):
    def __init__(self):
        self._successful = {}

    @staticmethod
    def _execution_id(context, plan, proposal, governance):
        return fingerprint({
            'context_reference': context.reference,
            'planning_reference': plan.reference,
            'proposal_reference': proposal.reference,
            'governance_reference': governance.reference,
            'authorization_reference': governance.authorization_reference,
            'authorized_action': (governance.authorized_action.value
                                  if governance.authorized_action is not None else None),
            'authorized_payload': export(governance.authorized_payload),
            'execution_policy_version': EXECUTION_POLICY_VERSION,
        })

    @staticmethod
    def _result(*, execution_id, status, reason, state, action=None,
                target_id=None, operation=None, requested_value=None,
                applied_value=None, mutation=False, replay=False,
                governance=None, authorization_reference=None):
        snapshot = clone_state(state)
        state_ref = fingerprint(snapshot.to_dict())
        return ExecutionResult(
            requested_action=action or Action.REQUEST_APPROVAL,
            authorized_action=(action if status in (ExecutionStatus.SUCCEEDED,
                                ExecutionStatus.ALREADY_EXECUTED) else None),
            execution_status=status,
            state_before_reference=state_ref,
            state_after_reference=state_ref,
            reason=reason,
            governance_reference=(governance.reference if governance is not None else None),
            execution_policy_version=EXECUTION_POLICY_VERSION,
            execution_id=execution_id,
            target_id=target_id or 'UNAVAILABLE',
            operation=operation or 'UNAVAILABLE',
            requested_value=requested_value,
            applied_value=applied_value,
            state_version_before=state.state_version,
            state_version_after=snapshot.state_version,
            mutation_applied=mutation,
            idempotent_replay=replay,
            authorization_reference=authorization_reference,
            resulting_state=snapshot,
        )

    def execute(self, decision_context, planning_result, proposed_decision,
                governance_decision, industrial_state):
        if type(decision_context) is not DecisionContext:
            raise ValueError('Expected DecisionContext')
        if type(planning_result) is not PlanningResult:
            raise ValueError('Expected PlanningResult')
        if type(proposed_decision) is not ProposedDecision:
            raise ValueError('Expected ProposedDecision')
        if type(governance_decision) is not GovernanceDecision:
            raise ValueError('Expected GovernanceDecision')
        if type(industrial_state) is not IndustrialState:
            raise ValueError('Expected IndustrialState')

        context, plan, proposal, governance = (
            decision_context, planning_result, proposed_decision, governance_decision)
        execution_id = self._execution_id(context, plan, proposal, governance)
        observation = context.observation
        target_id, operation = observation['target_id'], observation['operation']
        requested_value = observation['requested_value']

        if execution_id in self._successful:
            prior = self._successful[execution_id]
            result = self._result(
                execution_id=execution_id, status=ExecutionStatus.ALREADY_EXECUTED,
                reason='ALREADY_EXECUTED: deterministic authorization was applied once; replay caused no mutation.',
                state=prior.resulting_state, action=prior.authorized_action,
                target_id=prior.target_id, operation=prior.operation,
                requested_value=prior.requested_value, applied_value=prior.applied_value,
                replay=True, governance=governance,
                authorization_reference=governance.authorization_reference)
            return result

        before = clone_state(industrial_state)

        if governance.status == GovernanceStatus.APPROVAL_REQUIRED:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.PENDING_APPROVAL,
                reason='PENDING_APPROVAL: governance did not authorize execution; no human response is inferred.',
                state=before, action=proposal.selected_action,
                target_id=target_id, operation=operation, requested_value=requested_value,
                governance=governance)
        if governance.status != GovernanceStatus.APPROVED:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.REJECTED,
                reason=f'REJECTED: governance status {governance.status.value} is not executable approval.',
                state=before, action=proposal.selected_action,
                target_id=target_id, operation=operation, requested_value=requested_value,
                governance=governance)

        binding_errors = []
        if plan.context_fingerprint != context.reference or plan.context_version != context.context_version:
            binding_errors.append('PlanningResult context binding mismatch.')
        if proposal.context_reference != context.reference:
            binding_errors.append('ProposedDecision context binding mismatch.')
        if proposal.planning_reference != plan.reference or proposal.planning_policy_version != plan.planning_policy_version:
            binding_errors.append('ProposedDecision planning binding mismatch.')
        if governance.context_reference != context.reference or governance.proposal_reference != proposal.reference:
            binding_errors.append('GovernanceDecision inference-chain binding mismatch.')
        selected = next((candidate for candidate in plan.candidates
                         if candidate.action == proposal.selected_action and
                         candidate.reference == proposal.selected_candidate_reference), None)
        if selected is None or tuple(proposal.candidate_actions) != tuple(plan.candidates):
            binding_errors.append('Selected proposal is not the exact planner candidate set.')
        if (selected is not None and
                (governance.proposed_action != selected.action or
                 governance.authorized_action != selected.action or
                 export(governance.authorized_payload) != export(selected.payload))):
            binding_errors.append('Authorized action/payload differs from the exact proposal.')
        if not governance.authorization_reference:
            binding_errors.append('Governance authorization reference is missing.')
        if any(value != 'PASS' for value in governance.policy_checks.values()) or governance.violations:
            binding_errors.append('Governance checks are not all PASS or violations remain.')
        if governance.governance_policy_version != GOVERNANCE_POLICY_VERSION:
            binding_errors.append('Unsupported governance policy version.')
        if selected is not None and governance.authorization_reference:
            expected_reference = governance_authorization_reference(
                context, plan, proposal, selected.action, selected.payload,
                governance.policy_checks)
            if governance.authorization_reference != expected_reference:
                binding_errors.append('Governance authorization reference is invalid.')
        if binding_errors:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.REJECTED,
                reason='REJECTED: ' + ' '.join(binding_errors), state=before,
                action=governance.authorized_action or proposal.selected_action,
                target_id=target_id, operation=operation, requested_value=requested_value,
                governance=governance)

        if context.state_version is None or context.state_version != before.state_version:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.STALE_STATE,
                reason=(f'STALE_STATE: approved state version {context.state_version} does not match '
                        f'current version {before.state_version}; a new decision cycle is required.'),
                state=before, action=governance.authorized_action,
                target_id=target_id, operation=operation, requested_value=requested_value,
                governance=governance,
                authorization_reference=governance.authorization_reference)
        observable_context = observation['contextual_features']
        if (observable_context.get('operating_mode') != before.operating_mode.value or
                observable_context.get('production_state') != before.production_state.value):
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.STALE_STATE,
                reason='STALE_STATE: current production state/mode differs from the approved context.',
                state=before, action=governance.authorized_action,
                target_id=target_id, operation=operation, requested_value=requested_value,
                governance=governance,
                authorization_reference=governance.authorization_reference)

        action, payload = governance.authorized_action, governance.authorized_payload
        if action == Action.ALLOW:
            applied_value = payload.get('requested_value')
        elif action == Action.LIMIT:
            applied_value = payload.get('replacement_value')
            if applied_value is None:
                return self._result(
                    execution_id=execution_id, status=ExecutionStatus.REJECTED,
                    reason='REJECTED: approved LIMIT has no explicit replacement value; executor will not invent one.',
                    state=before, action=action, target_id=target_id, operation=operation,
                    requested_value=requested_value, governance=governance,
                    authorization_reference=governance.authorization_reference)
        else:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.UNSUPPORTED,
                reason=f'UNSUPPORTED: no IndustrialState transition semantics exist for {action.value}.',
                state=before, action=action, target_id=target_id, operation=operation,
                requested_value=requested_value, governance=governance,
                authorization_reference=governance.authorization_reference)

        if operation != 'set_speed' or payload.get('target_id') != target_id or payload.get('operation') != operation:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.UNSUPPORTED,
                reason='UNSUPPORTED: only exact bound set_speed transitions have state semantics.',
                state=before, action=action, target_id=target_id, operation=operation,
                requested_value=requested_value, governance=governance,
                authorization_reference=governance.authorization_reference)
        if action == Action.ALLOW and applied_value != requested_value:
            return self._result(
                execution_id=execution_id, status=ExecutionStatus.REJECTED,
                reason='REJECTED: ALLOW payload value differs from the approved request.',
                state=before, action=action, target_id=target_id, operation=operation,
                requested_value=requested_value, governance=governance,
                authorization_reference=governance.authorization_reference)
        if action == Action.LIMIT:
            check = context.capabilities.operational_validity.check
            if (check is None or not isinstance(applied_value, (int, float)) or isinstance(applied_value, bool) or
                    not check.minimum <= applied_value <= check.maximum or
                    payload.get('allowed_min') != check.minimum or payload.get('allowed_max') != check.maximum):
                return self._result(
                    execution_id=execution_id, status=ExecutionStatus.REJECTED,
                    reason='REJECTED: LIMIT replacement is not explicitly bounded by the approved current range.',
                    state=before, action=action, target_id=target_id, operation=operation,
                    requested_value=requested_value, governance=governance,
                    authorization_reference=governance.authorization_reference)

        after = clone_state(before)
        target_before = after.asset_states[target_id]
        after.update_asset_state(target_id, current_value=applied_value, last_operation=operation)
        mutation = after.asset_states[target_id] != target_before
        result = ExecutionResult(
            requested_action=action,
            authorized_action=action,
            execution_status=ExecutionStatus.SUCCEEDED,
            state_before_reference=fingerprint(before.to_dict()),
            state_after_reference=fingerprint(after.to_dict()),
            reason=('SUCCEEDED: exact governance-authorized set_speed payload was applied to a cloned '
                    f'IndustrialState; mutation_applied={mutation}.'),
            governance_reference=governance.reference,
            execution_policy_version=EXECUTION_POLICY_VERSION,
            execution_id=execution_id,
            target_id=target_id,
            operation=operation,
            requested_value=requested_value,
            applied_value=applied_value,
            state_version_before=before.state_version,
            state_version_after=after.state_version,
            mutation_applied=mutation,
            idempotent_replay=False,
            authorization_reference=governance.authorization_reference,
            resulting_state=after,
        )
        self._successful[execution_id] = result
        return result
