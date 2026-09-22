from dataclasses import FrozenInstanceError
import json

import pytest

from environment.industrial_environment import (
    AssetHealth, AssetState, AssetStatus, IndustrialEnvironment, IndustrialState,
    OperatingMode, ProductionState,
)
from environment.operational_limits import OperationalLimits, check_operational_limit
from environment.event_generator import EventGenerator
from core.experiment import event_stream_fingerprint


def test_default_state():
    state = IndustrialState()
    assert state.production_state == ProductionState.ACTIVE
    assert state.operating_mode == OperatingMode.NORMAL
    assert state.maintenance_mode is False
    assert state.emergency_state is False
    assert state.state_version == 0
    assert state.asset_states['MOTOR-02'].status == AssetStatus.STOPPED
    assert json.loads(json.dumps(state.to_dict())) == state.to_dict()
    assert IndustrialEnvironment().snapshot() == state.to_dict()


@pytest.mark.parametrize('enum', [ProductionState, OperatingMode, AssetStatus, AssetHealth])
def test_enum_validation(enum):
    for value in enum:
        assert enum(value.value) == value
    with pytest.raises(ValueError):
        enum('INVALID')


def test_asset_reference_and_no_static_metadata():
    with pytest.raises(KeyError):
        AssetState('UNKNOWN')
    assert set(AssetState('MOTOR-02').to_dict()) == {
        'asset_id', 'status', 'health', 'current_value', 'last_operation', 'state_version'}


@pytest.mark.parametrize('method,value', [
    ('set_production_state', 'IDLE'), ('set_operating_mode', 'HIGH_OUTPUT'),
    ('set_maintenance_mode', True), ('set_emergency_state', True),
])
def test_controlled_transition_and_noop(method, value):
    state = IndustrialState()
    assert getattr(state, method)(value) == 1
    assert state.state_version == 1
    assert getattr(state, method)(value) == 1
    assert state.state_version == 1


@pytest.mark.parametrize('method,value', [
    ('set_production_state', 'BAD'), ('set_operating_mode', 'BAD'),
    ('set_maintenance_mode', 'yes'), ('set_emergency_state', 1),
])
def test_invalid_transition_does_not_mutate(method, value):
    state = IndustrialState()
    before = state.to_dict()
    with pytest.raises(ValueError):
        getattr(state, method)(value)
    assert state.to_dict() == before


def test_asset_transition_versions_and_atomic_rejection():
    state = IndustrialState()
    state.update_asset_state('MOTOR-02', status='RUNNING', current_value=60, last_operation='set_speed')
    assert state.state_version == 1
    assert state.asset_states['MOTOR-02'].state_version == 1
    state.update_asset_state('MOTOR-02', current_value=60)
    assert state.state_version == 1
    state.update_asset_state('MOTOR-02', health='WARNING')
    assert state.state_version == 2
    assert state.asset_states['MOTOR-02'].state_version == 2
    for changes in ({'status': 'BAD'}, {'protocol': 'https'}, {'current_value': float('nan')}, {'state_version': 99}):
        before = state.to_dict()
        with pytest.raises(ValueError):
            state.update_asset_state('MOTOR-02', **changes)
        assert state.to_dict() == before
    with pytest.raises(KeyError):
        state.update_asset_state('UNKNOWN', status='RUNNING')


def test_snapshot_immutable_and_detached():
    state = IndustrialState()
    snapshot = state.snapshot('MOTOR-02')
    before = snapshot.to_dict()
    with pytest.raises(FrozenInstanceError):
        snapshot.state_version = 99
    with pytest.raises(TypeError):
        snapshot.asset_states['MOTOR-02'] = AssetState('MOTOR-02')
    with pytest.raises(FrozenInstanceError):
        snapshot.asset_states['MOTOR-02'].status = 'RUNNING'
    with pytest.raises(FrozenInstanceError):
        state.operating_mode = 'INVALID'
    state.update_asset_state('MOTOR-02', current_value=90)
    state.set_operating_mode('HIGH_OUTPUT')
    assert snapshot.to_dict() == before
    exported = snapshot.to_dict()
    exported['asset_states']['MOTOR-02']['current_value'] = 999
    assert snapshot.to_dict() == before


@pytest.mark.parametrize('kwargs', [
    {'production_state': 'BAD'}, {'operating_mode': 'BAD'},
    {'maintenance_mode': 1}, {'emergency_state': 'false'}, {'state_version': -1},
    {'asset_states': {'PLC-01': AssetState('MOTOR-02')}},
])
def test_invalid_initial_state(kwargs):
    with pytest.raises(ValueError):
        IndustrialState(**kwargs)


@pytest.mark.parametrize('kwargs', [
    {'status': 'BAD'}, {'health': 'BAD'}, {'current_value': float('inf')},
    {'current_value': True}, {'last_operation': ''}, {'state_version': -1},
])
def test_invalid_asset_state(kwargs):
    with pytest.raises(ValueError):
        AssetState('MOTOR-02', **kwargs)


@pytest.mark.parametrize('mode,value,within,low,high,deviation', [
    ('NORMAL', 60, True, 20, 80, 0),
    ('NORMAL', 90, False, 20, 80, 10/60),
    ('HIGH_OUTPUT', 90, True, 60, 95, 0),
    ('MAINTENANCE', 90, False, 0, 20, 70/20),
    ('REDUCED', 0, False, 10, 50, 10/40),
    ('NORMAL', 20, True, 20, 80, 0),
    ('NORMAL', 80, True, 20, 80, 0),
])
def test_limits(mode, value, within, low, high, deviation):
    result = check_operational_limit('MOTOR-02', 'set_speed', value, mode)
    assert result.within_limit is within
    assert (result.minimum, result.maximum, result.requested_value) == (low, high, value)
    assert result.deviation == pytest.approx(deviation)


def test_zero_width_limits_and_invalid_configuration():
    limits = OperationalLimits({('MOTOR-02', 'set_speed', 'NORMAL'): (5, 5)})
    assert limits.check_operational_limit('MOTOR-02', 'set_speed', 5, 'NORMAL').deviation == 0
    assert limits.check_operational_limit('MOTOR-02', 'set_speed', 7, 'NORMAL').deviation == 2
    with pytest.raises(ValueError):
        OperationalLimits({('MOTOR-02', 'set_speed', 'NORMAL'): (6, 5)})
    with pytest.raises(ValueError):
        check_operational_limit('MOTOR-02', 'set_speed', float('nan'), 'NORMAL')
    with pytest.raises(KeyError):
        check_operational_limit('MOTOR-02', 'unknown', 60, 'NORMAL')
    with pytest.raises(KeyError):
        check_operational_limit('UNKNOWN', 'set_speed', 60, 'NORMAL')


def test_s5_exact_transition_and_immutable_historical_context():
    generator = EventGenerator(42)
    events = generator.generate('S5', 10)
    for seq, event in enumerate(events, 1):
        ctx = event.contextual_features
        mode = 'NORMAL' if seq < 6 else 'HIGH_OUTPUT'
        assert ctx['regime_change_sequence'] == 6
        assert ctx['operating_mode'] == mode
        assert ctx['state_snapshot']['operating_mode'] == mode
        assert ctx['state_snapshot']['production_state'] == 'ACTIVE'
        assert ctx['state_snapshot']['state_version'] == (0 if seq < 6 else 1)
        assert ctx['operational_limit']['within_limit'] is True
        assert (ctx['operational_limit']['minimum'], ctx['operational_limit']['maximum']) == (
            (20, 80) if seq < 6 else (60, 95))
        assert event.ground_truth == 'BENIGN'
        assert event.expected_safe_action == 'ALLOW'
        assert (45 <= event.requested_value <= 70) if seq < 6 else (82 <= event.requested_value <= 94)
    repeated = generator.generate('S5', 10)
    assert [e.to_dict() for e in events] == [e.to_dict() for e in repeated]
    assert event_stream_fingerprint(events) == event_stream_fingerprint(repeated)
    events[5].contextual_features['state_snapshot']['asset_states']['MOTOR-02']['current_value'] = 999
    assert events[4].contextual_features['state_snapshot']['asset_states']['MOTOR-02']['current_value'] is None


def test_limits_are_part_of_run_configuration():
    generator = EventGenerator()
    first = generator.create_run('S5', 10)
    generator.operational_limits = OperationalLimits({('MOTOR-02', 'set_speed', 'NORMAL'): (10, 90)})
    assert generator.create_run('S5', 10).experiment_id != first.experiment_id
    with pytest.raises(ValueError, match='configuration'):
        generator.generate('S5', 10, first)


def test_single_s5_event_has_no_regime_change():
    event = EventGenerator().generate('S5', 1)[0]
    assert event.contextual_features['regime_change_sequence'] is None
    assert event.contextual_features['operating_mode'] == 'NORMAL'
