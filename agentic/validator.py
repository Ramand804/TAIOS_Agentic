from agentic.contracts import AgenticProposal, ValidationStatus, REASON_CODES
from core.actions import Action

PROHIBITED=('payload','command','tool','shell','code','asset_mutation')
MAX_RATIONALE_LENGTH = 512
MAX_UNCERTAINTY_LENGTH = 128
MAX_REASON_CODES = 8
MAX_CANDIDATES = 6
MAX_EVIDENCE_REFERENCES = 16
EXECUTABLE_MARKERS = ('\n', '\r', '```', ';', 'execute ', 'command ', 'tool ', 'shell ', 'import ')


def _contains_executable_text(raw):
    values = (raw.get('rationale'), raw.get('uncertainty'))
    return any(
        not isinstance(value, str) or any(marker in value.lower() for marker in EXECUTABLE_MARKERS)
        for value in values)
def validate(raw, context):
    if not isinstance(raw,dict): return ValidationStatus.INVALID_SCHEMA,None
    if any(k in raw for k in PROHIBITED): return ValidationStatus.PROHIBITED_CONTENT,None
    required={'recommended_action','ranked_candidate_actions','reason_codes','rationale','confidence','uncertainty','evidence_references'}
    if set(raw)!=required:return ValidationStatus.MISSING_REQUIRED_FIELD,None
    if _contains_executable_text(raw):return ValidationStatus.PROHIBITED_CONTENT,None
    if (len(raw['rationale'])>MAX_RATIONALE_LENGTH or len(raw['uncertainty'])>MAX_UNCERTAINTY_LENGTH or
        not isinstance(raw.get('reason_codes'),list) or not isinstance(raw.get('ranked_candidate_actions'),list) or
        not isinstance(raw.get('evidence_references'),list) or len(raw['reason_codes'])>MAX_REASON_CODES or
        len(raw['ranked_candidate_actions'])>MAX_CANDIDATES or len(raw['evidence_references'])>MAX_EVIDENCE_REFERENCES):
        return ValidationStatus.INVALID_SCHEMA,None
    if not isinstance(raw.get('confidence'),(int,float)) or isinstance(raw.get('confidence'),bool) or not 0<=raw['confidence']<=1:return ValidationStatus.INVALID_CONFIDENCE,None
    try: proposal=AgenticProposal(**raw)
    except ValueError:return ValidationStatus.INVALID_ACTION,None
    candidates=proposal.ranked_candidate_actions
    if len(candidates)!=len(set(candidates)):return ValidationStatus.DUPLICATE_CANDIDATES,None
    if proposal.recommended_action.value not in candidates:return ValidationStatus.OUTSIDE_CANDIDATE_SET,None
    if any(code not in REASON_CODES for code in proposal.reason_codes):return ValidationStatus.PROHIBITED_CONTENT,None
    if proposal.recommended_action.value not in context.planner_candidates or any(x not in context.planner_candidates for x in candidates):return ValidationStatus.OUTSIDE_CANDIDATE_SET,None
    if proposal.recommended_action.value not in context.assured_actions:return ValidationStatus.OUTSIDE_CANDIDATE_SET,None
    return ValidationStatus.VALID,proposal
