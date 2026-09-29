"""V2 transaction facade reusing V1 checkpoint/restore semantics."""
from dataclasses import dataclass, field

@dataclass
class TAIOSTransactionContext:
    pipeline: object
    completed_stages: list[str] = field(default_factory=list)
    failure_stage: str | None = None
    committed: bool = False
    def begin(self):
        self.checkpoints=self.pipeline._transaction_checkpoints()
        return self
    def stage_complete(self, stage):
        if self.committed: raise RuntimeError('Transaction is already committed')
        if stage in self.completed_stages: raise RuntimeError(f'Transaction stage replayed: {stage}')
        self.completed_stages.append(stage)
    def commit(self): self.committed=True
    def rollback(self, stage):
        self.failure_stage=stage
        self.pipeline._rollback_transaction(self.checkpoints)
