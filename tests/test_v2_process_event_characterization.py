from copy import deepcopy
import pytest
from core.taios_pipeline import TAIOSPipeline, PipelineProcessingError
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from agentic.semantic_fingerprint import fingerprint,pipeline_state_fingerprint

def events(s='S2'):
 g=EventGenerator(42,observable_state=True); r=g.create_run(s,10); return g.generate(s,10,r)

def test_success_and_approval_required_are_committed_valid_outcomes():
 p=TAIOSPipeline(); state=IndustrialState(); before=pipeline_state_fingerprint(p)
 first=p.process_event(events()[4],state); assert first.execution_result.execution_status.value=='SUCCEEDED'
 after_success=pipeline_state_fingerprint(p); assert before!=after_success
 pending=p.process_event(events()[5],first.state_after)
 assert pending.execution_result.execution_status.value=='PENDING_APPROVAL'
 assert events()[5].event_id in p._processed_events and pending.experience_reference and pending.feedback_reference

def test_public_replay_is_idempotent_execution_behavior():
 event=events()[4]; p=TAIOSPipeline(); first=p.process_event(event,IndustrialState()); replay=p.process_event(event,first.state_after)
 assert replay.execution_result.execution_status.value=='ALREADY_EXECUTED'
 assert replay.execution_result.execution_id==first.execution_result.execution_id

def test_failure_after_mutable_trust_rolls_back_and_does_not_commit(monkeypatch):
 p=TAIOSPipeline(); event=events()[4]; before=pipeline_state_fingerprint(p)
 def fail(*args,**kwargs): raise ValueError('injected')
 monkeypatch.setattr(p.risk_agent,'assess',fail)
 with pytest.raises(PipelineProcessingError) as caught:p.process_event(event,IndustrialState())
 assert caught.value.failure.stage=='risk_assessment'
 assert pipeline_state_fingerprint(p)==before and event.event_id not in p._processed_events

def test_evaluator_metadata_does_not_change_runtime_result():
 event=events()[4]; clean=TAIOSPipeline().process_event(event,IndustrialState())
 changed=deepcopy(event); changed.ground_truth='unsafe'; changed.expected_safe_action='BLOCK'
 observed=TAIOSPipeline().process_event(changed,IndustrialState())
 assert fingerprint(clean.to_dict())==fingerprint(observed.to_dict())

def test_deterministic_sequence_oracles_cover_unexplained_drift_and_known_regime():
    for scenario in ('S2','S5'):
        p=TAIOSPipeline(); state=IndustrialState(); trace=[]
        for event in events(scenario):
            result=p.process_event(event,state); state=result.state_after
            trace.append((fingerprint(result.to_dict()),pipeline_state_fingerprint(p),result.drift_assessment.status.value,result.assurance_assessment.status.value,result.proposed_decision.selected_action.value,result.execution_result.execution_status.value))
        again=TAIOSPipeline(); other=IndustrialState(); replay=[]
        for event in events(scenario):
            result=again.process_event(event,other); other=result.state_after
            replay.append((fingerprint(result.to_dict()),pipeline_state_fingerprint(again),result.drift_assessment.status.value,result.assurance_assessment.status.value,result.proposed_decision.selected_action.value,result.execution_result.execution_status.value))
        assert trace==replay
    assert any(item[2]=='UNEXPLAINED_PERSISTENT_DRIFT' for item in trace) is False

def test_s2_persistent_drift_and_s5_known_regime_are_actual_distinct_outcomes():
    def statuses(scenario):
        p=TAIOSPipeline(); state=IndustrialState(); rows=[]
        for event in events(scenario):
            row=p.process_event(event,state); state=row.state_after; rows.append(row)
        return rows
    s2=statuses('S2'); s5=statuses('S5')
    assert any(r.drift_assessment.status.value=='UNEXPLAINED_PERSISTENT_DRIFT' for r in s2)
    assert any(r.drift_assessment.status.value=='KNOWN_REGIME_CHANGE' for r in s5)
    assert all(r.adaptation_decision is not None for r in s2+s5)

def test_late_outcome_failure_rolls_back_memory_feedback_and_processed_event(monkeypatch):
    p=TAIOSPipeline(); event=events()[4]; before=pipeline_state_fingerprint(p)
    def fail(*args,**kwargs): raise ValueError('late')
    monkeypatch.setattr(p.outcome_observer,'observe',fail)
    with pytest.raises(PipelineProcessingError): p.process_event(event,IndustrialState())
    assert pipeline_state_fingerprint(p)==before and event.event_id not in p._processed_events

def test_semantically_outside_limit_is_valid_completed_transaction():
    p=TAIOSPipeline(); state=IndustrialState(); rows=[]
    for event in events('S2')[:6]:
        row=p.process_event(event,state); state=row.state_after; rows.append(row)
    row=rows[-1]
    assert row.operational_semantic_assessment.operational_validity=='OUTSIDE_LIMIT'
    assert row.execution_result.execution_status.value=='PENDING_APPROVAL'
    assert row.event_id in p._processed_events and row.experience_reference and row.feedback_reference

@pytest.mark.parametrize('seam', ['feedback_memory','behavioral_adapter'])
def test_late_feedback_or_adaptation_failure_rolls_back(monkeypatch,seam):
    p=TAIOSPipeline(); event=events('S2')[5]; before=pipeline_state_fingerprint(p)
    if seam=='feedback_memory': monkeypatch.setattr(p.feedback_memory,'append',lambda *_: (_ for _ in ()).throw(ValueError('feedback')))
    else: monkeypatch.setattr(p.behavioral_adapter,'evaluate',lambda *_: (_ for _ in ()).throw(ValueError('adapt')))
    with pytest.raises(PipelineProcessingError): p.process_event(event,IndustrialState())
    assert pipeline_state_fingerprint(p)==before and event.event_id not in p._processed_events

def test_result_construction_failure_is_rollback_protected(monkeypatch):
    import core.taios_pipeline as module
    p=TAIOSPipeline(); event=events()[4]; before=pipeline_state_fingerprint(p); original=module.PipelineResult
    monkeypatch.setattr(module,'PipelineResult',lambda **_: (_ for _ in ()).throw(ValueError('result')))
    with pytest.raises(PipelineProcessingError): p.process_event(event,IndustrialState())
    assert pipeline_state_fingerprint(p)==before and event.event_id not in p._processed_events
    monkeypatch.setattr(module,'PipelineResult',original)
    assert p.process_event(event,IndustrialState()).event_id==event.event_id
