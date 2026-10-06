from industrial.runtime_types import IndustrialDecisionContext
from industrial.runtime.foundation import IndustrialSemanticModel,IndustrialAuthorization
class IndustrialContextBuilder:
 def __init__(self,semantics=None,authorization=None):self.semantics=semantics or IndustrialSemanticModel();self.authorization=authorization or IndustrialAuthorization()
 def build(self,event,state):return IndustrialDecisionContext(event,state,self.semantics.assess(event,state),self.authorization.assess(event))
