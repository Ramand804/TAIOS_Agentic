from dataclasses import dataclass
from enum import Enum
from core.actions import Action
from core.decision_contracts import Record, freeze, texts
from core.risk_input import text_value
from core.trust_evidence import unit_value

class ValidationStatus(str, Enum):
    VALID='VALID'; INVALID_SCHEMA='INVALID_SCHEMA'; INVALID_ACTION='INVALID_ACTION'; OUTSIDE_CANDIDATE_SET='OUTSIDE_CANDIDATE_SET'; DUPLICATE_CANDIDATES='DUPLICATE_CANDIDATES'; INVALID_CONFIDENCE='INVALID_CONFIDENCE'; PROHIBITED_CONTENT='PROHIBITED_CONTENT'; MISSING_REQUIRED_FIELD='MISSING_REQUIRED_FIELD'; TIMEOUT='TIMEOUT'; PROVIDER_ERROR='PROVIDER_ERROR'; MODEL_UNAVAILABLE='MODEL_UNAVAILABLE'

REASON_CODES=frozenset({'MOCK','SEMANTICS','AUTHORIZATION','TRUST','THREAT','RISK','DRIFT','ASSURANCE','UNCERTAINTY'})

@dataclass(frozen=True,kw_only=True)
class AgenticInput(Record):
    observation: object; semantics: object; authorization_status: str; trust_summary: object; threat_summary: object; risk_summary: object; drift_summary: object; adaptation_summary: object; assured_actions: tuple[str,...]; planner_candidates: tuple[str,...]; evidence_references: tuple[str,...]; baseline_action: str | None = None; memory_context: tuple[object,...] = ()
    def __post_init__(self):
        object.__setattr__(self,'observation',freeze(self.observation));
        for n in ('semantics','trust_summary','threat_summary','risk_summary','drift_summary','adaptation_summary'): object.__setattr__(self,n,freeze(getattr(self,n)))
        object.__setattr__(self,'memory_context',tuple(freeze(item) for item in self.memory_context))
        text_value(self.authorization_status,'authorization_status'); object.__setattr__(self,'assured_actions',tuple(Action(x).value for x in self.assured_actions)); object.__setattr__(self,'planner_candidates',tuple(Action(x).value for x in self.planner_candidates)); object.__setattr__(self,'evidence_references',texts(self.evidence_references)); object.__setattr__(self,'baseline_action',Action(self.baseline_action).value if self.baseline_action is not None else None)

@dataclass(frozen=True,kw_only=True)
class AgenticProposal(Record):
    recommended_action: Action; ranked_candidate_actions: tuple[str,...]; reason_codes: tuple[str,...]; rationale: str; confidence: float; uncertainty: str; evidence_references: tuple[str,...]
    def __post_init__(self):
        object.__setattr__(self,'recommended_action',Action(self.recommended_action)); object.__setattr__(self,'ranked_candidate_actions',tuple(Action(x).value for x in self.ranked_candidate_actions)); object.__setattr__(self,'reason_codes',texts(self.reason_codes)); text_value(self.rationale,'rationale'); unit_value(self.confidence,'confidence'); text_value(self.uncertainty,'uncertainty'); object.__setattr__(self,'evidence_references',texts(self.evidence_references))
