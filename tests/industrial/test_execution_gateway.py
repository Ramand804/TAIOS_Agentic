from industrial.execution import ExecutionGateway
from industrial.process.model import ManufacturingCell
def test_legacy_direct_execution_is_disabled_without_mutation():
 cell=ManufacturingCell(); before=cell.state
 result=ExecutionGateway(cell,lambda:None).execute(object(),object(),object())
 assert not result.executed and result.reason=='LEGACY_DIRECT_EXECUTION_DISABLED'
 assert cell.state==before
