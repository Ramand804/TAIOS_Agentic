"""Observe only effects exposed by ExecutionResult and IndustrialState."""
from core.decision_contracts import ExecutionResult, ExecutionStatus
from core.experiment import fingerprint
from core.observed_outcome import ObservedOutcome, OutcomeStatus
from core.runtime_inputs import OBSERVABLE_FIELDS
from environment.industrial_environment import IndustrialState


class OutcomeObserver:
    _STATUS_MAP = {
        ExecutionStatus.PENDING_APPROVAL: OutcomeStatus.PENDING_EXTERNAL_APPROVAL,
        ExecutionStatus.REJECTED: OutcomeStatus.EXECUTION_REJECTED,
        ExecutionStatus.UNSUPPORTED: OutcomeStatus.UNSUPPORTED_EXECUTION,
        ExecutionStatus.STALE_STATE: OutcomeStatus.STALE_EXECUTION_PREVENTED,
        ExecutionStatus.ALREADY_EXECUTED: OutcomeStatus.DUPLICATE_EXECUTION_PREVENTED,
        ExecutionStatus.DENIED: OutcomeStatus.EXECUTION_DENIED,
        ExecutionStatus.FAILED: OutcomeStatus.OUTCOME_PARTIALLY_OBSERVED,
    }

    def observe(self, observation, execution_result, state_before, state_after,
                *, event_reference):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection')
        if type(execution_result) is not ExecutionResult:
            raise ValueError('Expected ExecutionResult')
        if type(state_before) is not IndustrialState or type(state_after) is not IndustrialState:
            raise ValueError('Expected IndustrialState before and after')
        if execution_result.resulting_state.to_dict() != state_after.to_dict():
            raise ValueError('Execution result/state-after mismatch')
        if execution_result.target_id != observation['target_id'] or execution_result.operation != observation['operation']:
            raise ValueError('Execution result scope mismatch')
        if execution_result.requested_value != observation['requested_value']:
            raise ValueError('Execution request mismatch')
        if execution_result.state_version_before != state_before.state_version:
            raise ValueError('Execution state-before version mismatch')
        if execution_result.state_version_after != state_after.state_version:
            raise ValueError('Execution state-after version mismatch')
        if (execution_result.state_before_reference != fingerprint(state_before.to_dict()) or
                execution_result.state_after_reference != fingerprint(state_after.to_dict())):
            raise ValueError('Execution state reference mismatch')
        if execution_result.mutation_applied != (state_before.to_dict() != state_after.to_dict()):
            raise ValueError('Execution mutation flag disagrees with observable state')
        status = execution_result.execution_status
        if status == ExecutionStatus.SUCCEEDED:
            outcome_status = (OutcomeStatus.EXECUTED_MUTATION_OBSERVED
                              if execution_result.mutation_applied else
                              OutcomeStatus.EXECUTED_NOOP_OBSERVED)
        else:
            outcome_status = self._STATUS_MAP.get(status, OutcomeStatus.OUTCOME_PARTIALLY_OBSERVED)
        target_state = state_after.asset_states[observation['target_id']]
        pending = status == ExecutionStatus.PENDING_APPROVAL
        effects = (
            f'Execution status observed: {status.value}.',
            f'State version observed: {state_before.state_version} -> {state_after.state_version}.',
            f'Target {observation["target_id"]} value observed as {target_state.current_value!r}.',
            f'Mutation observed: {execution_result.mutation_applied}.',
        )
        unresolved = (('external_approval_decision', 'future_execution_effect') if pending else
                      ('physical_process_effects_not_modeled',)
                      if status == ExecutionStatus.SUCCEEDED else
                      ('future_external_effects',))
        return ObservedOutcome(
            event_reference=event_reference,
            execution_reference=execution_result.reference,
            target_id=observation['target_id'], operation=observation['operation'],
            requested_value=observation['requested_value'],
            applied_value=execution_result.applied_value,
            execution_status=status.value,
            state_version_before=state_before.state_version,
            state_version_after=state_after.state_version,
            mutation_observed=execution_result.mutation_applied,
            resulting_observable_value=target_state.current_value,
            operating_mode_after=state_after.operating_mode.value,
            production_state_after=state_after.production_state.value,
            outcome_status=outcome_status, observable_effects=effects,
            unresolved_outcome_fields=unresolved)
