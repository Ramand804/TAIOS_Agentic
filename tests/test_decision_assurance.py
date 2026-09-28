from dataclasses import FrozenInstanceError

import pytest

from core.actions import Action
from core.assurance_assessment import AssuranceCausalEffect, AssuranceStatus
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator


def episode(scenario, *, enabled=True, seed=42):
    g=EventGenerator(seed,observable_state=True); run=g.create_run(scenario,10)
    return TAIOSPipeline(assurance_enabled=enabled).run_episode(g.generate(scenario,10,run),seed=seed)


def test_contracts_immutable_deterministic_and_subset():
    row=episode('S2').pipeline_results[6]; a=row.assurance_assessment
    assert a == episode('S2').pipeline_results[6].assurance_assessment
    with pytest.raises(FrozenInstanceError): a.status=AssuranceStatus.AUTONOMY_CONFIRMED
    assert set(a.assured_permitted_actions)-{'REQUEST_APPROVAL'} <= set(a.existing_permitted_actions)


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1,7)])
def test_subset_and_no_increase_in_autonomy_across_scenarios(scenario):
    on,off=episode(scenario,enabled=True),episode(scenario,enabled=False)
    for a,b in zip(on.pipeline_results,off.pipeline_results):
        assured={x for x,v in a.assured_authority_assessment.action_authority.items() if v=='PERMITTED'}-{'REQUEST_APPROVAL'}
        existing={x for x,v in a.authority_assessment.action_authority.items() if v=='PERMITTED'}
        assert assured <= existing
        assert not (a.execution_result.execution_status.value=='SUCCEEDED' and b.execution_result.execution_status.value!='SUCCEEDED')


def test_s2_is_already_restricted_upstream_and_s5_is_exempt():
    s2=episode('S2').pipeline_results
    assert all(r.assurance_assessment.causal_effect==AssuranceCausalEffect.ALREADY_RESTRICTED_UPSTREAM for r in s2[5:])
    assert [r.proposed_decision.selected_action.value for r in s2[5:]]==['REQUEST_APPROVAL']*5
    s5=episode('S5').pipeline_results
    assert all(r.assurance_assessment.status==AssuranceStatus.AUTONOMY_CONFIRMED for r in s5[5:])
    assert [r.proposed_decision.selected_action.value for r in s5[5:]]==['ALLOW']*5


def test_off_reproduces_actions_and_risk_alone_or_trust_alone_do_not_restrict():
    on,off=episode('S2'),episode('S2',enabled=False)
    assert [r.proposed_decision for r in on.pipeline_results]==[r.proposed_decision for r in off.pipeline_results]
    assert on.pipeline_results[0].assurance_assessment.causal_effect==AssuranceCausalEffect.ASSESSMENT_ONLY
    assert off.pipeline_results[0].assurance_assessment.causal_effect==AssuranceCausalEffect.ASSURANCE_DISABLED


def test_no_trust_and_rule_based_compatibility():
    from evaluation.baseline_framework import create_pipeline
    g=EventGenerator(42,observable_state=True); run=g.create_run('S5',10); events=g.generate('S5',10,run)
    no_trust=create_pipeline('TAIOS_NO_TRUST').run_episode(events,seed=42)
    rule=create_pipeline('RULE_BASED').run_episode(events,seed=42)
    assert {r.trust_assessment.composite_trust for r in no_trust.pipeline_results}=={.8}
    assert all(r.assurance_assessment.causal_effect==AssuranceCausalEffect.ASSURANCE_DISABLED for r in rule.pipeline_results)
