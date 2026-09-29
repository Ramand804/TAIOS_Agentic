"""Stable semantic fingerprints for transaction characterization."""
from dataclasses import is_dataclass, fields
from enum import Enum
from hashlib import sha256
import json

def normalize(value):
    if isinstance(value, Enum): return value.value
    if is_dataclass(value): return {field.name:normalize(getattr(value,field.name)) for field in fields(value)}
    if hasattr(value,'to_dict'): return normalize(value.to_dict())
    if isinstance(value,dict): return {str(k):normalize(v) for k,v in sorted(value.items(),key=lambda x:str(x[0]))}
    if isinstance(value,(list,tuple)): return [normalize(x) for x in value]
    if isinstance(value,set): return sorted(normalize(x) for x in value)
    if type(value).__name__=='mappingproxy': return normalize(dict(value))
    return value

def fingerprint(value):
    return sha256(json.dumps(normalize(value),sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

def pipeline_state_fingerprint(pipeline):
    """Checkpoint-equivalent transaction state; excludes object identities only."""
    return fingerprint({'trust':pipeline.trust_agent._checkpoint(),'counts':dict(pipeline._entity_observations),'execution':pipeline.execution_agent._checkpoint(),'threat':pipeline.threat_evidence_model._checkpoint(),'correlation':pipeline.correlation_evidence_model._checkpoint(),'memory':pipeline.memory._checkpoint(),'feedback':pipeline.feedback_memory._checkpoint(),'drift':pipeline.drift_detector._checkpoint(),'adaptation':pipeline.behavioral_adapter._checkpoint(),'processed':pipeline._processed_events})
