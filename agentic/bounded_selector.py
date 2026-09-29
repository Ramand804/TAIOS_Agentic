"""V2-only, fail-closed selection among V1 planner candidates."""
from dataclasses import dataclass, replace
from agents.decision_agent import DecisionAgent
from core.actions import Action
from core.decision_context import DecisionContext
from core.decision_contracts import ProposedDecision
from core.planning_result import PlanningResult
from agentic.contracts import AgenticProposal, ValidationStatus

@dataclass(frozen=True, kw_only=True)
class AgenticSelectionProvenance:
    deterministic_v1_action: str | None
    planner_candidate_actions: tuple[str, ...]
    assured_permitted_actions: tuple[str, ...]
    llm_recommended_action: str | None
    validation_status: ValidationStatus
    selection_accepted: bool
    selected_action: str | None
    selection_source: str
    fallback_used: bool
    fallback_reason: str | None

class BoundedAgenticSelector:
    """Makes no policy decision: it only chooses an existing assured candidate."""
    def __init__(self, decision_agent=None):
        self.decision_agent = decision_agent or DecisionAgent()

    @staticmethod
    def _permitted(assurance, authority):
        assured = tuple(getattr(assurance, 'assured_permitted_actions', ()))
        authority_map = getattr(authority, 'action_authority', {})
        return tuple(action for action in assured if authority_map.get(action) == 'PERMITTED')

    def select(self, decision_context, planning_result, validated_agentic_proposal,
               assurance_result, authority_state, validation_status=ValidationStatus.VALID):
        if type(decision_context) is not DecisionContext or type(planning_result) is not PlanningResult:
            raise ValueError('Expected canonical V1 DecisionContext and PlanningResult')
        baseline = self.decision_agent.decide(decision_context, planning_result)
        candidates = tuple(candidate.action.value for candidate in planning_result.candidates)
        permitted = self._permitted(assurance_result, authority_state)
        recommended = (validated_agentic_proposal.recommended_action.value
                       if type(validated_agentic_proposal) is AgenticProposal else None)
        reason = None
        accepted = (
            validation_status == ValidationStatus.VALID and
            recommended is not None and recommended in candidates and recommended in permitted and
            planning_result.context_fingerprint == decision_context.reference and
            planning_result.context_version == decision_context.context_version)
        if not accepted:
            reason = 'VALIDATION_OR_ENVELOPE_REJECTED'
            selected, source = baseline, 'AGENTIC_FALLBACK'
        elif baseline.selected_action is not None and recommended == baseline.selected_action.value:
            selected, source = baseline, 'AGENTIC_VALIDATED_BASELINE'
        else:
            candidate = next(item for item in planning_result.candidates if item.action.value == recommended)
            selected = replace(
                baseline, selected_action=candidate.action,
                selected_candidate_reference=candidate.reference,
                primary_reason=('Validated agentic recommendation selected an existing planner candidate '
                                'inside the assurance and authority envelope.'),
                alternatives_considered=tuple(
                    f'{item.action.value}: planner-permitted alternative.' for item in planning_result.candidates
                    if item.reference != candidate.reference))
            source = 'AGENTIC_VALIDATED'
        provenance = AgenticSelectionProvenance(
            deterministic_v1_action=(baseline.selected_action.value if baseline.selected_action else None),
            planner_candidate_actions=candidates, assured_permitted_actions=permitted,
            llm_recommended_action=recommended, validation_status=ValidationStatus(validation_status),
            selection_accepted=accepted, selected_action=(selected.selected_action.value if selected.selected_action else None),
            selection_source=source, fallback_used=not accepted, fallback_reason=reason)
        return selected, provenance
