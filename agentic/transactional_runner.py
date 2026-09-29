"""Sequential V2 parity runner using protected V1 stage implementation."""
from core.experiment import fingerprint
from core.pipeline_result import PipelineProcessingError
from environment.industrial_environment import IndustrialState
from agentic.transaction import TAIOSTransactionContext

class V2TransactionalRunner:
    def __init__(self, pipeline): self.pipeline=pipeline
    def process_event(self, event, state, *, decision_selector=None):
        if type(state) is not IndustrialState: raise ValueError('Expected IndustrialState')
        key=getattr(event,'event_id',None); input_reference=fingerprint(state.to_dict())
        # Preserve V1's already-committed replay contract rather than reimplement it.
        prior=self.pipeline._processed_events.get(key)
        if prior is not None:
            return self.pipeline.process_event(event,state)
        transaction=TAIOSTransactionContext(self.pipeline).begin()
        stage={'stage':'event_validation'}
        try:
            result=self.pipeline._process_event_stages(event,state,input_reference,key,stage,decision_selector)
            transaction.stage_complete('result_construction')
            transaction.commit()
            return result
        except PipelineProcessingError: raise
        except (AttributeError,KeyError,TypeError,ValueError) as exc:
            transaction.rollback(stage['stage'])
            self.pipeline._failure(stage['stage'],exc,event,state)
