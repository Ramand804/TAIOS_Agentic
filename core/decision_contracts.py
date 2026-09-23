"""Immutable future decision-stage records. No planning or execution logic."""
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
import math
from types import MappingProxyType

from core.actions import Action
from core.experiment import fingerprint
from core.risk_input import text_value


def freeze(value):
    if isinstance(value, Mapping):
        if any(not isinstance(k,str) for k in value): raise ValueError('Object keys must be strings')
        return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(tuple,list)): return tuple(freeze(v) for v in value)
    if value is None or isinstance(value,(str,bool,int)): return value
    if isinstance(value,float) and math.isfinite(value): return value
    raise ValueError('Expected finite JSON-compatible data')


def export(value):
    if isinstance(value,Enum): return value.value
    if isinstance(value,Mapping): return {k:export(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [export(v) for v in value]
    if hasattr(value,'to_inference_dict'): return value.to_inference_dict()
    if hasattr(value,'to_dict'): return value.to_dict()
    return value


def texts(value):
    if isinstance(value,str): raise ValueError('Expected a sequence of descriptions')
    result=tuple(value)
    for item in result: text_value(item,'description')
    return result


class Record:
    def to_dict(self): return {f.name:export(getattr(self,f.name)) for f in fields(self)}
    @property
    def reference(self): return fingerprint(self.to_dict())


@dataclass(frozen=True, kw_only=True)
class CandidateAction(Record):
    action: Action
    payload: object
    rationale: str
    safety_effect: str
    operational_impact: str
    reversibility: str
    requires_approval: bool
    policy_constraints: tuple[str,...]
    evidence_basis: tuple[str,...]
    unresolved_prerequisites: tuple[str,...]
    capability_reference: str
    planning_policy_version: str

    def __post_init__(self):
        object.__setattr__(self,'action',Action(self.action))
        if not isinstance(self.payload,Mapping): raise ValueError('payload must be an object')
        object.__setattr__(self,'payload',freeze(self.payload))
        for name in ('rationale','safety_effect','operational_impact','reversibility','capability_reference','planning_policy_version'):
            text_value(getattr(self,name),name)
        if type(self.requires_approval) is not bool: raise ValueError('requires_approval must be bool')
        for name in ('policy_constraints','evidence_basis','unresolved_prerequisites'):
            object.__setattr__(self,name,texts(getattr(self,name)))


@dataclass(frozen=True, kw_only=True)
class ProposedDecision(Record):
    selected_action: Action | None
    selected_candidate_reference: str | None
    candidate_actions: tuple[CandidateAction,...]
    primary_reason: str
    evidence_summary: tuple[str,...]
    trust_basis: str
    risk_basis: str
    uncertainty: tuple[str,...]
    policy_basis: tuple[str,...]
    alternatives_considered: tuple[str,...]
    context_reference: str
    decision_policy_version: str

    def __post_init__(self):
        candidates=tuple(self.candidate_actions)
        if any(type(c) is not CandidateAction for c in candidates): raise ValueError('Expected CandidateAction records')
        if len({c.reference for c in candidates})!=len(candidates): raise ValueError('Duplicate candidate')
        object.__setattr__(self,'candidate_actions',candidates)
        if self.selected_action is None:
            if candidates or self.selected_candidate_reference is not None: raise ValueError('No selection requires no admissible candidates')
        else:
            object.__setattr__(self,'selected_action',Action(self.selected_action))
            if not any(c.action==self.selected_action and c.reference==self.selected_candidate_reference for c in candidates):
                raise ValueError('Selected candidate must belong to candidate set')
        for name in ('primary_reason','trust_basis','risk_basis','context_reference','decision_policy_version'):
            text_value(getattr(self,name),name)
        for name in ('evidence_summary','uncertainty','policy_basis','alternatives_considered'):
            object.__setattr__(self,name,texts(getattr(self,name)))

    @property
    def status(self): return 'PROPOSED' if self.selected_action is not None else 'NO_ADMISSIBLE_ACTION'

    def to_dict(self):
        result=super().to_dict()
        result['status']=self.status
        result['selected_payload']=next((export(c.payload) for c in self.candidate_actions if c.reference==self.selected_candidate_reference),None)
        return result


class GovernanceStatus(str,Enum):
    APPROVED='APPROVED'
    VETOED='VETOED'
    APPROVAL_REQUIRED='APPROVAL_REQUIRED'
    OVERRIDDEN='OVERRIDDEN'


@dataclass(frozen=True, kw_only=True)
class GovernanceDecision(Record):
    status: GovernanceStatus
    proposed_action: Action
    authorized_action: Action | None
    authorized_payload: object | None
    policy_checks: object
    violations: tuple[str,...]
    reason: str
    context_reference: str
    proposal_reference: str
    authorization_reference: str | None
    governance_policy_version: str

    def __post_init__(self):
        object.__setattr__(self,'status',GovernanceStatus(self.status))
        object.__setattr__(self,'proposed_action',Action(self.proposed_action))
        if self.authorized_action is not None: object.__setattr__(self,'authorized_action',Action(self.authorized_action))
        if not isinstance(self.policy_checks,Mapping) or any(v not in ('PASS','FAIL','UNKNOWN') for v in self.policy_checks.values()):
            raise ValueError('Invalid policy checks')
        object.__setattr__(self,'policy_checks',freeze(self.policy_checks))
        object.__setattr__(self,'violations',texts(self.violations))
        allowed=self.status in (GovernanceStatus.APPROVED,GovernanceStatus.OVERRIDDEN)
        if allowed:
            if self.authorized_action is None or not isinstance(self.authorized_payload,Mapping): raise ValueError('Authorization requires action/payload')
            text_value(self.authorization_reference,'authorization_reference')
            if not self.policy_checks or any(v!='PASS' for v in self.policy_checks.values()) or self.violations:
                raise ValueError('Authorization requires passing checks and no violations')
            if (self.status==GovernanceStatus.APPROVED)!=(self.authorized_action==self.proposed_action):
                raise ValueError('Approved action must match; override must differ')
            object.__setattr__(self,'authorized_payload',freeze(self.authorized_payload))
        elif any(v is not None for v in (self.authorized_action,self.authorized_payload,self.authorization_reference)):
            raise ValueError('Veto/pending cannot carry execution authorization')
        for name in ('reason','context_reference','proposal_reference','governance_policy_version'):
            text_value(getattr(self,name),name)


class ExecutionStatus(str,Enum):
    SUCCEEDED='SUCCEEDED'
    DENIED='DENIED'
    PENDING_APPROVAL='PENDING_APPROVAL'
    REJECTED='REJECTED'
    UNSUPPORTED='UNSUPPORTED'
    FAILED='FAILED'


@dataclass(frozen=True, kw_only=True)
class ExecutionResult(Record):
    requested_action: Action
    authorized_action: Action | None
    execution_status: ExecutionStatus
    state_before_reference: str | None
    state_after_reference: str | None
    reason: str
    governance_reference: str | None
    execution_policy_version: str

    def __post_init__(self):
        object.__setattr__(self,'requested_action',Action(self.requested_action))
        object.__setattr__(self,'execution_status',ExecutionStatus(self.execution_status))
        if self.authorized_action is not None: object.__setattr__(self,'authorized_action',Action(self.authorized_action))
        for name in ('state_before_reference','state_after_reference','governance_reference'):
            if getattr(self,name) is not None: text_value(getattr(self,name),name)
        if self.execution_status in (ExecutionStatus.SUCCEEDED,ExecutionStatus.DENIED) and (self.authorized_action is None or self.governance_reference is None):
            raise ValueError('Success requires an authorized action and governance reference')
        if self.execution_status==ExecutionStatus.DENIED and self.authorized_action!=Action.BLOCK:
            raise ValueError('Denied execution represents authorized BLOCK')
        if self.execution_status==ExecutionStatus.PENDING_APPROVAL and self.authorized_action not in (None,Action.REQUEST_APPROVAL):
            raise ValueError('Pending approval cannot execute the original action')
        for name in ('reason','execution_policy_version'): text_value(getattr(self,name),name)
