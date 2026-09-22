"""Run deterministic CLI smoke checks in separate processes; keep artifacts in a temporary directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(scenario, count, directory, hash_seed, seed=42):
    env = dict(os.environ, PYTHONHASHSEED=str(hash_seed))
    subprocess.run([sys.executable, str(ROOT / 'main.py'), '--scenario', scenario,
                    '--events', str(count), '--seed', str(seed), '--log-dir', str(directory)],
                   cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    folders = list(directory.iterdir())
    assert len(folders) == 1
    folder = folders[0]
    blobs = {name: (folder / name).read_bytes() for name in
             ('experiment.json', 'scenario_manifest.json', 'events.jsonl')}
    rows = [json.loads(line) for line in blobs['events.jsonl'].splitlines()]
    manifest = json.loads(blobs['scenario_manifest.json'])
    assert len(rows) == count
    transition = manifest['transition_sequence']
    assert transition is None or 1 <= transition <= count
    for seq, row in enumerate(rows, 1):
        post = transition is not None and seq >= transition
        label, action = ('BENIGN', 'ALLOW')
        if scenario in ('S2', 'S3') and post: label, action = ('MALICIOUS', 'BLOCK')
        if scenario == 'S4': label, action = ('SUSPICIOUS', 'REQUEST_APPROVAL')
        if scenario == 'S6' and post: label, action = ('MALICIOUS', 'ISOLATE')
        assert (row['ground_truth'], row['expected_safe_action']) == (label, action)
        assert row['provenance']['phase'] == manifest['phases'][1 if post else 0]
        assert row['sequence_number'] == seq
        if scenario == 'S2': assert row['contextual_features']['compromise_event'] == transition
        if scenario == 'S5':
            context = row['contextual_features']
            assert context['regime_change_sequence'] == transition
            assert context['operating_mode'] == ('HIGH_OUTPUT' if post else 'NORMAL')
            assert context['operational_limit']['within_limit']
    return blobs


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='taios-audit-') as temporary:
        base = Path(temporary)
        for scenario in [f'S{i}' for i in range(1, 7)]:
            for count in (1, 2, 3, 10):
                a = base / f'{scenario}-{count}-a'
                b = base / f'{scenario}-{count}-b'
                first = run(scenario, count, a, 1)
                assert first == run(scenario, count, b, 999)
                assert first == run(scenario, count, a, 123)
            changed = run(scenario, 10, base / f'{scenario}-changed', 5, seed=123)
            initial_meta = json.loads(first['experiment.json'])
            changed_meta = json.loads(changed['experiment.json'])
            assert initial_meta['experiment_id'] != changed_meta['experiment_id']
            assert initial_meta['event_stream_fingerprint'] != changed_meta['event_stream_fingerprint']
            results.append({'scenario': scenario, 'counts': [1, 2, 3, 10], 'status': 'PASS',
                            'experiment_id': initial_meta['experiment_id'],
                            'fingerprint': initial_meta['event_stream_fingerprint']})
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
