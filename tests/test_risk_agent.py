from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from agents.base_agent import BaseAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.risk_assessment import RiskAssessment
from core.risk_input import COMPONENTS, RiskConfig
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.validators import EventIntegrityError
from evaluation.evaluate_trust import assess_observations
from intelligence.risk_input_builder import build_risk_input
from intelligence.risk_model import RiskModel
from tests.test_risk_inputs import run


def semantic(result):
    return json.dumps(result.to_inference_dict(), sort_keys=True, allow_nan=False)


@pytest.mark.parametrize('scenario', ['S1','S2','S3','S5'])
def test_direct_equivalence_replay_and_immutability(scenario):
    events, trusts, inputs = run(scenario)
    agent=RiskAgent()
    assert isinstance(agent, BaseAgent)
    for event, trust, item in zip(events, trusts, inputs):
        observation=runtime_observation(event)
        before=deepcopy(observation); trust_before=trust.to_dict()
        result=agent.assess(observation, trust)
        assert type(result) is RiskAssessment
        assert result.to_dict() == RiskModel().evaluate(item).to_dict()
        assert semantic(result) == semantic(agent.assess(observation,trust))
        assert semantic(result) == semantic(RiskAgent().assess(observation,trust))
        assert observation == before and trust.to_dict() == trust_before
        assert result.trust_state_version == trust.trust_state_version
        assert result.model_version == 'day3c-model-v1'
        assert result.coverage == .45
        assert result.threat_probability is result.anomaly_score is None
        assert result.threat_available is result.anomaly_available is False
        with pytest.raises(FrozenInstanceError): result.risk_score=0


def test_audit_isolation_and_copy_safety():
    events,trusts,_=run()
    o=runtime_observation(events[0]); trust=trusts[0]; agent=RiskAgent()
    plain=agent.assess(o,trust)
    for identifier,seq in [('opaque-A',1),('opaque-B',999)]:
        audit=AuditCorrelation(identifier,seq)
        result=agent.assess(o,replace(trust,audit=audit),correlation_metadata=audit)
        assert result.audit == audit
        assert semantic(result) == semantic(plain)
        exported=result.to_dict(); exported['audit']['event_id']='mutated'
        assert result.audit.event_id == identifier
        with pytest.raises(FrozenInstanceError): result.audit.event_id='mutated'
    # With no trust correlation, metadata is only an output attachment.
    attached=agent.assess(o,trust,correlation_metadata=AuditCorrelation('output-only',2))
    assert semantic(attached) == semantic(plain)
    # Without an explicit request, upstream audit is not automatically copied.
    assert agent.assess(o,replace(trust,audit=AuditCorrelation('upstream',1))).audit is None


@pytest.mark.parametrize('audit', [{}, 'id', 3])
def test_invalid_audit(audit):
    events,trusts,_=run()
    with pytest.raises(ValueError,match='AuditCorrelation'):
        RiskAgent().assess(runtime_observation(events[0]),trusts[0],correlation_metadata=audit)


@pytest.mark.parametrize('audit', [AuditCorrelation('different',1), AuditCorrelation('same',2)])
def test_correlation_mismatch(audit):
    events,trusts,_=run()
    trust=replace(trusts[0],audit=AuditCorrelation('same',1))
    agent=RiskAgent(); o=runtime_observation(events[0])
    with pytest.raises(ValueError,match='correlation'):
        agent.assess(o,trust,correlation_metadata=audit)
    assert agent.assess(o,trust,correlation_metadata=trust.audit).audit == trust.audit


@pytest.mark.parametrize('expected', [-1, True, '1', 2])
def test_expected_version_rejection(expected):
    events,trusts,_=run()
    with pytest.raises(ValueError,match='version'):
        RiskAgent().assess(runtime_observation(events[0]),trusts[0],expected_trust_state_version=expected)


def test_version_assertion_and_explicit_freshness_limit():
    events,trusts,_=run(); agent=RiskAgent()
    o=runtime_observation(events[1])
    with pytest.raises(ValueError,match='version'):
        agent.assess(o,trusts[0],expected_trust_state_version=trusts[1].trust_state_version)
    result=agent.assess(o,trusts[1],expected_trust_state_version=2)
    assert result.trust_state_version == 2
    # No observation binding exists: same-source stale trust cannot be proven
    # stale without a caller assertion. This limitation must not be disguised.
    assert agent.assess(o,trusts[0]).trust_state_version == 1


def test_configuration_single_source_and_invalid_config():
    config=RiskConfig(dict(zip(COMPONENTS,(.3,.35,.2,.15))))
    events,trusts,_=run(); o=runtime_observation(events[0])
    result=RiskAgent(config=config).assess(o,trusts[0])
    expected=RiskModel().evaluate(build_risk_input(o,trusts[0],config=config))
    assert result.to_dict() == expected.to_dict()
    assert result.config is config
    assert result.to_dict()['configuration_fingerprint'] == config.fingerprint
    for invalid in ({},'config/risk.yaml',0):
        with pytest.raises(ValueError,match='RiskConfig'): RiskAgent(config=invalid)
    # There is no separate model configuration to mismatch with the builder.
    with pytest.raises(TypeError): RiskAgent(config=config,model_config=RiskConfig.load())


def test_validation_delegation():
    events,trusts,_=run(); o=runtime_observation(events[0]); agent=RiskAgent()
    with pytest.raises(ValueError,match='entity'):
        agent.assess(o,run('S5')[1][0])
    with pytest.raises(EventIntegrityError):
        agent.assess(dict(o,asset_criticality=.92),trusts[0])
    for invalid in (events[0],events[0].to_dict(),dict(o,scenario_id='hidden')):
        with pytest.raises(ValueError): agent.assess(invalid,trusts[0])
    for invalid in (None,trusts[0].to_dict()):
        with pytest.raises(ValueError,match='TrustAssessment'): agent.assess(o,invalid)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_hidden_labels_and_correlation_do_not_change_inference(scenario):
    events,trusts,_=run(scenario)
    original=[RiskAgent().assess(runtime_observation(e),t) for e,t in zip(events,trusts)]
    for event in events:
        event.ground_truth='MALICIOUS'; event.expected_safe_action='ISOLATE'; event.scenario_id='OTHER'
        event.provenance=replace(event.provenance,phase='OTHER',transition_type='OTHER',causal_tags=('OTHER',))
        event.contextual_features.update(anomaly_score=1,simulated_attack_probability=1,
            prior_device_trust=0,compromise_phase=True)
    changed=assess_observations(events,TrustAgent())
    for event,trust,before in zip(events,changed,original):
        audit=AuditCorrelation('OTHER',999)
        after=RiskAgent().assess(runtime_observation(event),replace(trust,audit=audit),correlation_metadata=audit)
        assert semantic(before) == semantic(after)


def test_diagnostics_and_missing_semantics():
    expected={'S1':{6:.492805122},'S2':{4:.514751411,5:.514542725,6:.516510317,7:.518506308,8:.520295547},
              'S3':{6:.532526835},'S5':{5:.514542725,6:.514332391,7:.514120821}}
    results={}
    for scenario,selected in expected.items():
        events,trusts,_=run(scenario)
        rows=[RiskAgent().assess(runtime_observation(e),t) for e,t in zip(events,trusts)]
        results[scenario]=rows
        for n,score in selected.items():
            assert rows[n-1].risk_score == pytest.approx(score,abs=5e-10)
            assert rows[n-1].coverage_details['status'] == 'INCOMPLETE'
            assert rows[n-1].component_contributions['ANOMALY'] == 0
    s2=results['S2']
    for a,b in zip(s2[4:7],s2[5:8]):
        assert a.composite_trust>b.composite_trust and a.distrust_score<b.distrust_score
        assert a.risk_score<b.risk_score and a.criticality_score==b.criticality_score==.91
    s3=results['S3'][5]
    assert s3.trust_evidence_coverage['BEHAVIOR']==('INSUFFICIENT',)
    assert any('Behavioral evidence is insufficient' in r for r in s3.reasons)
    s5=results['S5']
    assert s5[4].risk_score>s5[5].risk_score>s5[6].risk_score
