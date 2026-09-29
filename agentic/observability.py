from dataclasses import dataclass,field
from time import perf_counter
@dataclass
class WorkflowObservability:
    events:list=field(default_factory=list)
    def start(self,node): return node,perf_counter()
    def finish(self,token,outcome):
        node,started=token; self.events.append({'node':node,'outcome':outcome,'duration_seconds':perf_counter()-started})
    def semantic_view(self): return tuple((x['node'],x['outcome']) for x in self.events)
