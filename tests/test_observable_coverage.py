from core.runtime_inputs import runtime_observation
from core.orchestrator import Orchestrator
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.trust_evidence_extractor import TrustEvidenceExtractor


def behavior(observation):
    return TrustEvidenceExtractor().extract(observation)[2]


def test_s2_shared_state_and_projection():
    events=EventGenerator(observable_state=True).generate('S2',10)
    for i,e in enumerate(events):
        context=e.contextual_features
        assert context['state_snapshot']==IndustrialState().snapshot(e.target_id).to_dict()
        safe=runtime_observation(e)
        assert safe['contextual_features']=={'production_state':'ACTIVE','operating_mode':'NORMAL'}
        assert behavior(safe).direction == ('POSITIVE' if i<5 else 'NEGATIVE')


def test_generality_standalone_and_s3_missing_policy():
    extractor=TrustEvidenceExtractor()
    for sid in ('S2','S3','S5'):
        for e in EventGenerator(observable_state=True).generate(sid,10)[4:6]:
            safe=runtime_observation(e)
            # Input is an ordinary standalone dictionary with no scenario metadata.
            assert extractor.extract(dict(safe))==extractor.extract(safe)
            if sid=='S3':
                records=extractor.extract(safe)
                assert records[0].direction=='POSITIVE'
                assert records[2].direction=='NEUTRAL'
                assert 'MISSING_LIMIT' in records[2].reason
    safe=runtime_observation(EventGenerator(observable_state=True).generate('S2',1)[0])
    safe['requested_value']=90
    assert behavior(safe).direction=='NEGATIVE'
    safe['contextual_features']['operating_mode']='HIGH_OUTPUT'
    assert behavior(safe).direction=='POSITIVE'


def test_s5_current_state_and_generator_reset():
    generator=EventGenerator(observable_state=True)
    events=generator.generate('S5',10)
    for i,event in enumerate(events):
        safe=runtime_observation(event)
        assert safe['contextual_features']['operating_mode']==('NORMAL' if i<5 else 'HIGH_OUTPUT')
        assert event.contextual_features['state_snapshot']['operating_mode']==safe['contextual_features']['operating_mode']
        assert behavior(safe).direction=='POSITIVE'
    assert generator.generate('S2',1)[0].contextual_features['operating_mode']=='NORMAL'
    assert [e.to_dict() for e in events]==[e.to_dict() for e in generator.generate('S5',10)]


def test_enriched_leakage():
    extractor=TrustEvidenceExtractor()
    for sid in ('S2','S3','S5'):
        event=EventGenerator(observable_state=True).generate(sid,10)[5]
        before=extractor.extract(runtime_observation(event))
        event.ground_truth='OTHER'; event.expected_safe_action='OTHER'; event.provenance=None; event.scenario_id='OTHER'
        event.contextual_features.update(compromise_phase=False, anomaly_score=0, causal_tags=['other'], regime_change_sequence=99)
        assert extractor.extract(runtime_observation(event))==before


def test_frozen_and_enriched_runs_separate_and_deterministic(tmp_path):
    old=Orchestrator(log_dir=tmp_path)
    new=Orchestrator(log_dir=tmp_path,observable_state=True)
    old_events=old.run_scenario('S2',10)
    events=new.run_scenario('S2',10)
    assert old.experiment.experiment_id!=new.experiment.experiment_id
    assert 'operating_mode' not in old_events[0].contextual_features
    before=new.event_logger.path.read_bytes()
    assert [e.to_dict() for e in events]==[e.to_dict() for e in new.run_scenario('S2',10)]
    assert new.event_logger.path.read_bytes()==before
    assert old.experiment.generator_version=='day1c-step4-v1'
    assert new.experiment.generator_version=='day2c5-observable-v1'
