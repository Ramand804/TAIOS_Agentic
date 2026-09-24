"""Decision substrate: observable context, logical capabilities and prose policies."""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import yaml

from core.actions import Action
from core.decision_contracts import Record, freeze, export, texts
from core.experiment import fingerprint
from core.risk_input import text_value
from core.risk_assessment import RiskAssessment
from core.trust_assessment import TrustAssessment
from environment.industrial_environment import OperatingMode, validate_number
from environment.operational_limits import LimitCheck

VERSION='day4c7-context-v1'


class AuthorizationStatus(str,Enum):
    AUTHORIZED='AUTHORIZED'
    UNAUTHORIZED='UNAUTHORIZED'
    UNKNOWN='UNKNOWN'


@dataclass(frozen=True, kw_only=True)
class OperationalValidity(Record):
    operating_mode: str | None
    reference_id: str
    check: LimitCheck | None
    reason: str

    def __post_init__(self):
        if self.operating_mode is not None: OperatingMode(self.operating_mode)
        text_value(self.reference_id,'reference_id'); text_value(self.reason,'reason')
        if self.check is not None:
            if type(self.check) is not LimitCheck or self.operating_mode is None: raise ValueError('Check requires mode and LimitCheck')
            for name in ('minimum','maximum','requested_value','deviation'): validate_number(getattr(self.check,name),name)
            c=self.check
            if c.minimum>c.maximum or type(c.within_limit) is not bool or c.within_limit!=(c.minimum<=c.requested_value<=c.maximum):
                raise ValueError('Inconsistent limit check')
            expected=max(c.minimum-c.requested_value,0,c.requested_value-c.maximum)/(c.maximum-c.minimum or 1)
            if c.deviation!=expected: raise ValueError('Inconsistent deviation')

    @property
    def status(self):
        return 'UNKNOWN' if self.check is None else 'WITHIN_LIMIT' if self.check.within_limit else 'OUTSIDE_LIMIT'

    def to_dict(self):
        result=super().to_dict(); result['status']=self.status; return result


@dataclass(frozen=True, kw_only=True)
class CapabilityEnvelope(Record):
    source_id: str
    target_id: str
    operation: str
    observation_reference: str
    operational_validity: OperationalValidity
    capability_version: str = 'day4b-capabilities-v1'

    def __post_init__(self):
        for name in ('source_id','target_id','operation','observation_reference'): text_value(getattr(self,name),name)
        if type(self.operational_validity) is not OperationalValidity: raise ValueError('Expected OperationalValidity')
        if self.capability_version!='day4b-capabilities-v1': raise ValueError('Unsupported capability version')

    @property
    def supported_actions(self):
        # Logical representation only, not executor support or permission.
        return tuple(a for a in Action if a!=Action.ISOLATE and (a!=Action.LIMIT or self.operational_validity.check is not None))

    def to_dict(self):
        result=super().to_dict()
        result.update(supported_actions=[a.value for a in self.supported_actions],
            execution_implemented=False, external_approval_integration=False,
            monitoring_capability='LOGICAL_ONLY',approval_capability='LOGICAL_ONLY',
            isolation_capability='UNKNOWN',limit_capability='RANGE_ONLY' if self.operational_validity.check else 'UNKNOWN',
            reasons=['Logical capability is not authorization, admissibility or execution.',
                     'LIMIT exposes a range only; no safe transform or replacement value is selected.',
                     'Isolation and physical safety of denial/deferral are not established.'])
        return result


@dataclass(frozen=True, kw_only=True)
class PolicyDefinition(Record):
    policy_id: str
    name: str
    description: str
    enabled: bool

    def __post_init__(self):
        for name in ('policy_id','name','description'): text_value(getattr(self,name),name)
        if type(self.enabled) is not bool: raise ValueError('enabled must be boolean')


@dataclass(frozen=True, kw_only=True)
class PolicyContext(Record):
    observation_reference: str
    policies: tuple[PolicyDefinition,...]
    policy_version: str='day4b-prose-v1'

    def __post_init__(self):
        text_value(self.observation_reference,'observation_reference')
        policies=tuple(self.policies)
        if any(type(p) is not PolicyDefinition for p in policies) or len({p.policy_id for p in policies})!=len(policies):
            raise ValueError('Policies must have unique identifiers')
        object.__setattr__(self,'policies',tuple(sorted(policies,key=lambda p:p.policy_id)))
        if self.policy_version!='day4b-prose-v1': raise ValueError('Unsupported policy version')

    @property
    def authorization_status(self): return AuthorizationStatus.UNKNOWN

    def to_dict(self):
        result=super().to_dict()
        result.update(authorization_status=self.authorization_status.value,
            policy_facts={p.policy_id:{'enabled':p.enabled,'applicability':'UNKNOWN' if p.enabled else 'DISABLED',
                'executable':False} for p in self.policies},
            approval_requirement='UNKNOWN',autonomous_isolation_permission='UNKNOWN',
            reason='Configured policies are prose; no identity-operation grants or executable predicates exist.')
        return result


def load_policy_definitions(path=None):
    path=Path(path) if path is not None else Path(__file__).resolve().parents[1]/'config/policies.yaml'
    with path.open(encoding='utf-8') as stream: data=yaml.safe_load(stream)
    if not isinstance(data,dict) or set(data)!={'policies'} or not isinstance(data['policies'],list):
        raise ValueError('Expected policies list')
    result=[]
    for row in data['policies']:
        if not isinstance(row,dict) or set(row)!={'id','name','description','enabled'}: raise ValueError('Unsupported policy schema')
        result.append(PolicyDefinition(policy_id=row['id'],name=row['name'],description=row['description'],enabled=row['enabled']))
    if len({p.policy_id for p in result})!=len(result): raise ValueError('Duplicate policy id')
    return tuple(result)


@dataclass(frozen=True, kw_only=True)
class DecisionContext(Record):
    observation: object
    trust_assessment: TrustAssessment
    risk_assessment: RiskAssessment
    capabilities: CapabilityEnvelope
    policy_context: PolicyContext
    authorization_assessment: object = None
    permission_policy: object = None
    autonomous_authority_assessment: object = None
    authority_policy: object = None
    state_version: int | None = None
    context_version: str = VERSION

    def __post_init__(self):
        if not isinstance(self.observation,Mapping): raise ValueError('Expected safe observation object')
        if type(self.trust_assessment) is not TrustAssessment or type(self.risk_assessment) is not RiskAssessment:
            raise ValueError('Expected public assessment contracts')
        if self.trust_assessment.audit is not None or self.risk_assessment.audit is not None: raise ValueError('Audit must remain outside context')
        if type(self.capabilities) is not CapabilityEnvelope or type(self.policy_context) is not PolicyContext: raise ValueError('Invalid context components')
        if self.context_version!=VERSION: raise ValueError('Unsupported context version')
        if self.state_version is not None and (type(self.state_version) is not int or self.state_version<0): raise ValueError('Invalid state version')
        # Reuse approved projection/registry validation and compare supplied trust,
        # not model mathematics. Local import avoids new coupling in frozen code.
        from intelligence.risk_input_builder import build_risk_input
        o=export(self.observation)
        expected=build_risk_input(o,self.trust_assessment,config=self.risk_assessment.config)
        for name in ('source_id','target_id','operation','composite_trust','distrust_score','criticality_score',
                     'trust_state_version','trust_evidence_coverage','prior_only_dimensions'):
            if getattr(expected,name)!=getattr(self.risk_assessment,name): raise ValueError(f'Assessment mismatch: {name}')
        from core.authorization import (AuthorizationAssessment, PermissionPolicy,
                                        authorization_request_reference)
        assessment = self.authorization_assessment
        if assessment is None:
            if self.permission_policy is not None:
                raise ValueError('Permission policy requires an explicit authorization assessment')
        else:
            if type(assessment) is not AuthorizationAssessment:
                raise ValueError('Expected AuthorizationAssessment')
            policy = PermissionPolicy.load() if self.permission_policy is None else self.permission_policy
            if type(policy) is not PermissionPolicy:
                raise ValueError('Expected PermissionPolicy')
            for name in ('identity_id', 'source_id', 'target_id', 'operation'):
                if getattr(assessment, name) != o[name]:
                    raise ValueError(f'Authorization scope mismatch: {name}')
            if assessment.request_reference != authorization_request_reference(o):
                raise ValueError('Authorization request reference mismatch')
            if (assessment.authorization_policy_version != policy.policy_version or
                    assessment.permission_policy_reference != policy.reference):
                raise ValueError('Authorization policy reference/version mismatch')
            if not set(assessment.matched_rule_ids) <= {r.rule_id for r in policy.rules}:
                raise ValueError('Authorization matched rule is absent from policy')
            object.__setattr__(self, 'permission_policy', policy)
        ref=fingerprint(o)
        if self.capabilities.observation_reference!=ref or self.policy_context.observation_reference!=ref:
            raise ValueError('Observation reference mismatch')
        for name in ('source_id','target_id','operation'):
            if getattr(self.capabilities,name)!=o[name]: raise ValueError('Capability scope mismatch')
        validity=self.capabilities.operational_validity
        if validity.operating_mode!=o['contextual_features'].get('operating_mode'): raise ValueError('Capability mode mismatch')
        if validity.check is not None and validity.check.requested_value!=o['requested_value']: raise ValueError('Capability value mismatch')
        from core.autonomous_authority import AutonomousAuthorityAssessment, AuthorityPolicy
        authority = self.autonomous_authority_assessment
        if authority is None:
            if self.authority_policy is not None:
                raise ValueError('Authority policy requires an explicit authority assessment')
        else:
            if type(authority) is not AutonomousAuthorityAssessment:
                raise ValueError('Expected AutonomousAuthorityAssessment')
            authority_policy = AuthorityPolicy.load() if self.authority_policy is None else self.authority_policy
            if type(authority_policy) is not AuthorityPolicy:
                raise ValueError('Expected AuthorityPolicy')
            for name, actual in (('source_id', o['source_id']), ('identity_id', o['identity_id']),
                                 ('target_id', o['target_id']), ('operation', o['operation'])):
                if getattr(authority, name) != actual:
                    raise ValueError(f'Authority scope mismatch: {name}')
            if authority.authorization_status != self.authorization_status:
                raise ValueError('Authority/authorization status mismatch')
            if authority.operational_validity != validity.status:
                raise ValueError('Authority operational validity mismatch')
            if (authority.authority_policy_version != authority_policy.policy_version or
                    authority.authority_policy_fingerprint != authority_policy.reference):
                raise ValueError('Authority policy reference/version mismatch')
            if authority.context_input_reference != self.authority_input_reference:
                raise ValueError('Authority context input reference mismatch')
            policy_ids = {rule.rule_id for rule in authority_policy.rules}
            if any(not set(authority.matched_policy_ids[action.value]) <= policy_ids for action in Action):
                raise ValueError('Authority matched rule is absent from policy')
            object.__setattr__(self, 'authority_policy', authority_policy)
        object.__setattr__(self,'observation',freeze(o))

    @property
    def source_id(self): return self.observation['source_id']
    @property
    def target_id(self): return self.observation['target_id']
    @property
    def authorization_status(self):
        return (AuthorizationStatus.UNKNOWN if self.authorization_assessment is None
                else self.authorization_assessment.status)

    @property
    def authorization_policy_version(self):
        return (None if self.authorization_assessment is None
                else self.authorization_assessment.authorization_policy_version)

    @property
    def authority_input_reference(self):
        return fingerprint({
            'observation': export(self.observation),
            'trust_assessment': self.trust_assessment.to_inference_dict(),
            'risk_assessment': self.risk_assessment.to_inference_dict(),
            'capabilities': self.capabilities.to_dict(),
            'policy_context': self.policy_context.to_dict(),
            'authorization_assessment': export(self.authorization_assessment),
            'permission_policy': export(self.permission_policy),
            'state_version': self.state_version,
            'context_version': self.context_version,
        })

    def to_dict(self):
        result = super().to_dict()
        result.update(authorization_status=self.authorization_status.value,
                      authorization_policy_version=self.authorization_policy_version,
                      authorization_basis='LEGACY_UNKNOWN' if self.authorization_assessment is None else 'ASSESSMENT',
                      authority_basis='LEGACY_UNAVAILABLE' if self.autonomous_authority_assessment is None else 'ASSESSMENT')
        return result
