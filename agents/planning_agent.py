"""Provisional deterministic candidate generation; never action selection."""
from agents.base_agent import BaseAgent
from core.actions import Action
from core.decision_context import DecisionContext
from core.decision_contracts import CandidateAction, export
from core.planning_result import PlanningResult, PLANNING_VERSION


class PlanningAgent(BaseAgent):
    def plan(self, context):
        if type(context) is not DecisionContext:
            raise ValueError('Expected DecisionContext, not raw event or evaluation data')
        observation = context.observation
        capability = context.capabilities
        validity = capability.operational_validity
        supported = capability.supported_actions
        policy_facts = context.policy_context.to_dict()
        unresolved = [
            f'Authorization is {context.authorization_status.value}; operation permission is not established.',
            'Governance authorization and implemented execution capability are absent.',
        ]
        if validity.status == 'UNKNOWN':
            unresolved.append('Current operation/mode validity is unknown.')
        for key, fact in policy_facts['policy_facts'].items():
            if fact['enabled']:
                unresolved.append(f'{key}: policy applicability is {fact["applicability"]}; no executable predicate.')
        coverage = context.trust_assessment.evidence_coverage
        evidence = (
            f'Authorization: {context.authorization_status.value}.',
            f'Operational validity: {validity.status}; mode: {validity.operating_mode or "UNKNOWN"}.',
            f'Request: {observation["operation"]}, value {export(observation["requested_value"])}.',
            f'Trust: {context.trust_assessment.composite_trust:.12g}; direct evidence: ' +
                '; '.join(f'{dimension}={"/".join(signs)}' for dimension, signs in coverage.items()),
            f'Risk: {context.risk_assessment.risk_score}; weighted coverage: {context.risk_assessment.coverage:.12g}; not a confidence probability.',
        )
        if validity.check is not None:
            check = validity.check
            evidence += (f'Current range [{check.minimum},{check.maximum}]; deviation {check.deviation:.12g}.',)
        payload = {
            'source_id': context.source_id, 'target_id': context.target_id,
            'operation': observation['operation'], 'requested_value': export(observation['requested_value']),
            'operating_mode': validity.operating_mode, 'execution_ready': False,
        }
        candidates, exclusions = [], {}
        constraints = ('No execution without governance authorization.',
                       'Unresolved policy applicability is not policy compliance.',
                       'PROVISIONAL / UNCALIBRATED planning rules; no action ranking.')
        for action in Action:
            if action not in supported:
                exclusions[action.value] = 'Capability not established for this context.'
                continue
            if action == Action.LIMIT:
                if validity.status != 'OUTSIDE_LIMIT' or validity.check is None:
                    exclusions[action.value] = 'No observed current-mode range violation requiring a constrained alternative.'
                    continue
                limit_payload = dict(payload, allowed_min=validity.check.minimum,
                    allowed_max=validity.check.maximum, limit_reference=validity.reference_id,
                    replacement_value=None)
                candidates.append(CandidateAction(action=action, payload=limit_payload,
                    rationale=f'{observation["operation"]} value {validity.check.requested_value} is outside current {validity.operating_mode} range [{validity.check.minimum},{validity.check.maximum}]; range-only alternative for review.',
                    safety_effect='A reviewed bounded transformation could address the observed range violation; none is selected.',
                    operational_impact='Constrained operation effects remain unverified.',
                    reversibility='UNKNOWN: depends on the future exact transformation and process effects.',
                    requires_approval=True, policy_constraints=constraints, evidence_basis=evidence,
                    unresolved_prerequisites=tuple(unresolved)+(
                        'A reviewed safe transformation and exact replacement payload are required.',
                        'Scoped approval must resolve permission and transformation prerequisites; approval alone cannot establish safety.'),
                    capability_reference=capability.reference, planning_policy_version=PLANNING_VERSION))
            elif action == Action.REQUEST_APPROVAL:
                candidates.append(CandidateAction(action=action, payload=dict(payload, purpose='DEFER_FOR_REVIEW'),
                    rationale='Logical approval capability can represent review of unresolved authorization, policy and execution prerequisites; no operation is permitted.',
                    safety_effect='Represents deferral for review without authorizing the original request; physical hold safety is unknown.',
                    operational_impact='Review delay and interruption consequences require assessment.',
                    reversibility='UNKNOWN: deferral does not undo a process or guarantee a safe pause.',
                    requires_approval=True, policy_constraints=constraints, evidence_basis=evidence,
                    unresolved_prerequisites=tuple(unresolved)+(
                        'A reviewed hold/disposition envelope and external approval workflow are not implemented.',),
                    capability_reference=capability.reference, planning_policy_version=PLANNING_VERSION))
            elif action in (Action.ALLOW, Action.MONITOR):
                exclusions[action.value] = 'Permissive prerequisites are not established: explicit authorization, applicable policy clearance and executable permission envelope; monitoring cannot substitute for these.'
            elif action == Action.BLOCK:
                exclusions[action.value] = 'Logical denial exists, but a reviewed denial-impact/safety envelope and policy authority are not established.'
            else:
                exclusions[action.value] = 'Isolation requires established capability, impact review and policy authority; current contracts establish none.'
        return PlanningResult(candidates=tuple(candidates), context_fingerprint=context.reference,
            context_version=context.context_version, planning_policy_version=PLANNING_VERSION,
            unresolved_constraints=tuple(unresolved), exclusions=exclusions)
