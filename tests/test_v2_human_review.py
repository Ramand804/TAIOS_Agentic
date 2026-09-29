import pytest
from agentic.human_review import HumanReviewLifecycle, ReviewStatus
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState

def pending_result():
 g=EventGenerator(42,observable_state=True); r=g.create_run('S2',10); events=g.generate('S2',10,r)
 p=TAIOSPipeline(); first=p.process_event(events[4],IndustrialState()); return p.process_event(events[5],first.state_after)

def test_review_lifecycle_requires_explicit_human_response_and_never_executes():
 lifecycle=HumanReviewLifecycle(); request=lifecycle.create(pending_result())
 assert request.status is ReviewStatus.PENDING_HUMAN_REVIEW
 resolution=lifecycle.resolve(request,status='APPROVED',reviewer_id='reviewer-1',reason='Scoped review complete')
 assert resolution.status is ReviewStatus.APPROVED and resolution.execution_authorized is False

def test_review_lifecycle_cannot_synthesize_pending_or_accept_nonpending():
 lifecycle=HumanReviewLifecycle(); request=lifecycle.create(pending_result())
 with pytest.raises(ValueError): lifecycle.resolve(request,status='PENDING_HUMAN_REVIEW',reviewer_id='r',reason='x')
