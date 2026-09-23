"""Immutable candidate collection and exclusions; no selected action."""
from collections.abc import Mapping
from dataclasses import dataclass

from core.actions import Action
from core.decision_contracts import CandidateAction, Record, freeze, texts
from core.risk_input import text_value

PLANNING_VERSION = 'day4c-planning-v1'


@dataclass(frozen=True, kw_only=True)
class PlanningResult(Record):
    candidates: tuple[CandidateAction, ...]
    context_fingerprint: str
    context_version: str
    planning_policy_version: str
    unresolved_constraints: tuple[str, ...]
    exclusions: object

    def __post_init__(self):
        candidates = tuple(self.candidates)
        if any(type(c) is not CandidateAction for c in candidates):
            raise ValueError('Expected CandidateAction records')
        actions = tuple(c.action for c in candidates)
        if len(set(actions)) != len(actions):
            raise ValueError('Duplicate action candidates')
        if actions != tuple(a for a in Action if a in actions):
            raise ValueError('Candidates must use canonical serialization order')
        for name in ('context_fingerprint', 'context_version', 'planning_policy_version'):
            text_value(getattr(self, name), name)
        if self.planning_policy_version != PLANNING_VERSION or any(c.planning_policy_version != self.planning_policy_version for c in candidates):
            raise ValueError('Planning version mismatch')
        if not isinstance(self.exclusions, Mapping):
            raise ValueError('Expected exclusion reasons')
        excluded = {Action(k): v for k, v in self.exclusions.items()}
        if set(excluded) != set(Action)-set(actions):
            raise ValueError('Every non-candidate action requires an exclusion reason')
        for reason in excluded.values():
            text_value(reason, 'exclusion reason')
        object.__setattr__(self, 'candidates', candidates)
        object.__setattr__(self, 'unresolved_constraints', texts(self.unresolved_constraints))
        object.__setattr__(self, 'exclusions', freeze({a.value: excluded[a] for a in Action if a in excluded}))

    @property
    def status(self):
        return 'CANDIDATES_FOR_REVIEW' if self.candidates else 'NO_ADMISSIBLE_CANDIDATES'

    def to_dict(self):
        result = super().to_dict()
        result['status'] = self.status
        return result
