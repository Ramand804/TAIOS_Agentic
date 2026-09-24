"""Structural deterministic governance diagnostics; no evaluator-label join."""
import json
from collections import Counter, defaultdict
from dataclasses import replace

from agents.governance_agent import GovernanceAgent
from core.actions import Action
from core.decision_contracts import ProposedDecision
from core.planning_result import PlanningResult
from evaluation.evaluate_decision_agent import (
    DIAGNOSTICS, SCENARIOS, SEEDS, inference_rows,
)


def _synthetic_plan(context, candidate):
    return PlanningResult(
        candidates=(candidate,),
        context_fingerprint=context.reference,
        context_version=context.context_version,
        planning_policy_version=candidate.planning_policy_version,
        unresolved_constraints=('Synthetic governance prevention probe.',),
        exclusions={action.value: 'Excluded by synthetic governance probe.'
                    for action in Action if action != candidate.action},
    )


def _synthetic_proposal(template, context, plan, candidate):
    return ProposedDecision(
        selected_action=candidate.action,
        selected_candidate_reference=candidate.reference,
        candidate_actions=(candidate,),
        primary_reason='Synthetic governance prevention probe.',
        evidence_summary=template.evidence_summary,
        trust_basis=template.trust_basis,
        risk_basis=template.risk_basis,
        uncertainty=template.uncertainty,
        policy_basis=template.policy_basis,
        alternatives_considered=(),
        context_reference=context.reference,
        decision_policy_version=template.decision_policy_version,
        planning_reference=plan.reference,
        planning_policy_version=plan.planning_policy_version,
    )


def _prevention_metrics():
    _, context, plan, decision = inference_rows('S2')[4]
    agent = GovernanceAgent()
    binding = (
        agent.review(context, plan, replace(decision, context_reference='tampered')).status.value,
        agent.review(context, plan, replace(decision, planning_reference='tampered')).status.value,
    )
    unsupported = []
    for action in (Action.BLOCK, Action.ISOLATE):
        candidate = replace(
            plan.candidates[0], action=action,
            rationale=f'Synthetic injected {action.value}.',
            payload=dict(plan.candidates[0].to_dict()['payload']),
        )
        synthetic_plan = _synthetic_plan(context, candidate)
        proposal = _synthetic_proposal(decision, context, synthetic_plan, candidate)
        unsupported.append(agent.review(context, synthetic_plan, proposal).status.value)
    return {
        'binding_failure_prevention': {
            'prevented': sum(status == 'VETOED' for status in binding),
            'tested': len(binding), 'statuses': list(binding)},
        'unsupported_action_prevention': {
            'prevented': sum(status == 'VETOED' for status in unsupported),
            'tested': len(unsupported), 'statuses': unsupported,
            'actions': ['BLOCK', 'ISOLATE']},
    }


def evaluate(events_per_run=10):
    statuses = Counter()
    by_proposal = defaultdict(Counter)
    diagnostics = []
    agent = GovernanceAgent()
    for seed in SEEDS:
        for scenario in SCENARIOS:
            for event, context, plan, proposal in inference_rows(scenario, seed, events_per_run):
                governance = agent.review(context, plan, proposal)
                status = governance.status.value
                action = proposal.selected_action.value if proposal.selected_action is not None else 'NO_DECISION'
                statuses[status] += 1
                by_proposal[action][status] += 1
                if seed == 42 and event.sequence_number in DIAGNOSTICS.get(scenario, ()):
                    diagnostics.append({
                        'scenario': scenario, 'sequence': event.sequence_number,
                        'proposal': action,
                        'governance_status': status,
                        'authorized_action': (governance.authorized_action.value
                                              if governance.authorized_action is not None else None),
                        'policy_checks': governance.to_dict()['policy_checks'],
                        'check_reasons': governance.to_dict()['check_reasons'],
                        'authorization': context.authorization_status.value,
                        'authority': context.autonomous_authority_assessment.to_dict()['action_authority'],
                        'operational_validity': context.capabilities.operational_validity.to_dict(),
                        'trust': context.trust_assessment.composite_trust,
                        'risk': context.risk_assessment.risk_score,
                        'risk_coverage': context.risk_assessment.coverage,
                        'unresolved_requirements': list(proposal.uncertainty),
                        'governance_policy_version': governance.governance_policy_version,
                        'governance_fingerprint': governance.reference,
                        'governance_decision': governance.to_dict(),
                    })
    labels = ('APPROVED', 'APPROVAL_REQUIRED', 'VETOED', 'OVERRIDDEN')
    total = sum(statuses.values())
    diagnostics.sort(key=lambda row: (row['scenario'], row['sequence']))
    return {
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_reviews': total,
        'governance_distribution': {status: statuses[status] for status in labels},
        'distribution_by_proposed_action': {
            action: {status: counts[status] for status in labels}
            for action, counts in sorted(by_proposal.items())},
        'structural_metrics': {
            'approval_rate': statuses['APPROVED'] / total if total else None,
            'approval_required_rate': statuses['APPROVAL_REQUIRED'] / total if total else None,
            'veto_rate': statuses['VETOED'] / total if total else None,
            'override_rate': statuses['OVERRIDDEN'] / total if total else None,
            **_prevention_metrics(),
            'interpretation': 'Structural policy behavior only; not effectiveness against attacks.',
        },
        'diagnostics': diagnostics,
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True, indent=2, allow_nan=False))
