# V2 transaction model

V1 `TAIOSPipeline.process_event` remains authoritative for lifecycle semantics. Its protected helpers expose checkpoint capture, checkpoint restoration, result construction, processed-event commit, and each lifecycle boundary without changing scientific components. The sequential V2 runner and the full LangGraph workflow use those helpers, with their own transaction facade delegating checkpoint/rollback directly to the V1 helpers. Sequence parity is tested for S2 and S5, including result and scientific-state fingerprints.

LangGraph has no persistent checkpoint backend. Its state is orchestration-local and its transaction context rejects duplicate lifecycle stages. A processed-event replay delegates to V1's public replay behavior rather than repeating mutable scientific stages.
