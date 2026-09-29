from enum import Enum
class MockMode(str,Enum): VALID_PROPOSAL='VALID_PROPOSAL'; MALFORMED_OUTPUT='MALFORMED_OUTPUT'; UNKNOWN_ACTION='UNKNOWN_ACTION'; OUTSIDE_CANDIDATE_SET='OUTSIDE_CANDIDATE_SET'; TIMEOUT='TIMEOUT'; PROVIDER_ERROR='PROVIDER_ERROR'; EMPTY_RESPONSE='EMPTY_RESPONSE'
class MockLLM:
 def __init__(self,mode=MockMode.VALID_PROPOSAL):self.mode=MockMode(mode)
 def reason(self,input):
  if self.mode==MockMode.TIMEOUT: raise TimeoutError('mock timeout')
  if self.mode==MockMode.PROVIDER_ERROR: raise RuntimeError('mock provider error')
  if self.mode==MockMode.EMPTY_RESPONSE:return None
  if self.mode==MockMode.MALFORMED_OUTPUT:return {'bad':True}
  action='UNKNOWN' if self.mode==MockMode.UNKNOWN_ACTION else ('BLOCK' if self.mode==MockMode.OUTSIDE_CANDIDATE_SET else (input.baseline_action or input.planner_candidates[0]))
  return {'recommended_action':action,'ranked_candidate_actions':[action],'reason_codes':['MOCK'],'rationale':'Deterministic mock advisory.','confidence':.5,'uncertainty':'mock','evidence_references':list(input.evidence_references)}
