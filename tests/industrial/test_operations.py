from datetime import datetime, timezone

from industrial.audit import AppendOnlyAuditLog
from industrial.mqtt import MqttIndustrialAdapter, MqttIngestStatus
from industrial.observability import IndustrialReadModel
from industrial.persistence import IndustrialPersistence
from industrial.runtime.governance import IndustrialGovernance, OperatingMode
from industrial.trusted_runtime import build_trusted_runtime


N = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_mqtt_is_disconnected_fail_closed_and_has_no_execution_api():
    adapter = MqttIndustrialAdapter(object())
    assert adapter.ingest("taios/industrial/commands", "{}").status is MqttIngestStatus.DISCONNECTED
    assert not hasattr(adapter, "execute") and not hasattr(adapter, "write")


def test_mqtt_rejects_topics_and_malformed_payload_without_gateway_call():
    class Gateway:
        def ingest_command(self, _request):
            raise AssertionError("invalid input must not reach gateway")
    adapter = MqttIndustrialAdapter(Gateway())
    adapter.set_connected(True)
    assert adapter.ingest("other/topic", "{}").status is MqttIngestStatus.INVALID_TOPIC
    assert adapter.ingest("taios/industrial/commands", "not-json").status is MqttIngestStatus.MALFORMED_PAYLOAD


def test_audit_chain_detects_tampering_and_persistence_is_append_oriented(tmp_path):
    audit = AppendOnlyAuditLog()
    first = audit.append("ingest", {"event": "A"}, N)
    audit.append("decision", {"event": "A", "result": "BLOCK"}, N)
    assert audit.verify()
    object.__setattr__(first, "entry_hash", "bad")
    assert not audit.verify()

    storage = IndustrialPersistence(tmp_path / "industrial.sqlite")
    assert storage.append("ingest", {"id": "a"}, N) == 1
    assert storage.append("decision", {"id": "a"}, N) == 2
    assert [record["sequence"] for record in storage.records()] == [1, 2]
    storage.close()


def test_read_model_is_read_only_and_reports_runtime_state():
    runtime = build_trusted_runtime(IndustrialGovernance(OperatingMode.SIMULATION, lambda: N), lambda: N)
    read_model = IndustrialReadModel(runtime, AppendOnlyAuditLog(), lambda: N)
    snapshot = read_model.snapshot()
    assert snapshot["operating_mode"] == "SIMULATION" and snapshot["state_version"] == 0
    assert not hasattr(read_model, "execute") and not hasattr(read_model, "issue")
