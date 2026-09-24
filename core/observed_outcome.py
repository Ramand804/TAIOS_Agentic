"""Immutable label-free observation of simulator-visible post-execution effects."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, texts
from core.risk_input import text_value


OUTCOME_OBSERVER_VERSION = 'milestone7a-outcome-observer-v1'


class OutcomeStatus(str, Enum):
    EXECUTED_MUTATION_OBSERVED = 'EXECUTED_MUTATION_OBSERVED'
    EXECUTED_NOOP_OBSERVED = 'EXECUTED_NOOP_OBSERVED'
    PENDING_EXTERNAL_APPROVAL = 'PENDING_EXTERNAL_APPROVAL'
    EXECUTION_REJECTED = 'EXECUTION_REJECTED'
    UNSUPPORTED_EXECUTION = 'UNSUPPORTED_EXECUTION'
    STALE_EXECUTION_PREVENTED = 'STALE_EXECUTION_PREVENTED'
    DUPLICATE_EXECUTION_PREVENTED = 'DUPLICATE_EXECUTION_PREVENTED'
    EXECUTION_DENIED = 'EXECUTION_DENIED'
    OUTCOME_PARTIALLY_OBSERVED = 'OUTCOME_PARTIALLY_OBSERVED'


@dataclass(frozen=True, kw_only=True)
class ObservedOutcome(Record):
    event_reference: str
    execution_reference: str
    target_id: str
    operation: str
    requested_value: object
    applied_value: object
    execution_status: str
    state_version_before: int
    state_version_after: int
    mutation_observed: bool
    resulting_observable_value: object
    operating_mode_after: str
    production_state_after: str
    outcome_status: OutcomeStatus
    observable_effects: tuple[str, ...]
    unresolved_outcome_fields: tuple[str, ...]
    observer_version: str = OUTCOME_OBSERVER_VERSION

    def __post_init__(self):
        for name in ('event_reference', 'execution_reference', 'target_id', 'operation',
                     'execution_status', 'operating_mode_after', 'production_state_after',
                     'observer_version'):
            text_value(getattr(self, name), name)
        for name in ('state_version_before', 'state_version_after'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        if type(self.mutation_observed) is not bool:
            raise ValueError('mutation_observed must be boolean')
        object.__setattr__(self, 'outcome_status', OutcomeStatus(self.outcome_status))
        object.__setattr__(self, 'observable_effects', texts(self.observable_effects))
        unresolved = tuple(self.unresolved_outcome_fields)
        if any(not isinstance(value, str) or not value.strip() for value in unresolved):
            raise ValueError('unresolved_outcome_fields must contain nonempty text')
        object.__setattr__(self, 'unresolved_outcome_fields', unresolved)
        if self.observer_version != OUTCOME_OBSERVER_VERSION:
            raise ValueError('Unsupported outcome observer version')
        if self.outcome_status == OutcomeStatus.EXECUTED_MUTATION_OBSERVED and not self.mutation_observed:
            raise ValueError('Mutation outcome requires an observed mutation')
        if self.outcome_status == OutcomeStatus.EXECUTED_NOOP_OBSERVED and self.mutation_observed:
            raise ValueError('No-op outcome cannot contain mutation')
