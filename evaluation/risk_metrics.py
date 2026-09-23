"""Offline risk metrics. Labels and transition metadata are evaluation-only."""
import math
from collections import defaultdict
from core.risk_input import COMPONENTS
from evaluation.trust_metrics import mean, ratio, summarize

TOLERANCE = 1e-12


def comparison_key(row):
    return (row['source_id'], row['target_id'], row['operation'],
            tuple(row['component_availability'][k] for k in COMPONENTS))


def with_risk_deltas(records):
    previous = {}
    result = []
    for record in records:
        row = dict(record)
        key = comparison_key(row)
        before = previous.get(key)
        value = row['risk_score']
        row['risk_delta'] = None if before is None or value is None else value-before
        previous[key] = value  # Null breaks the chain; never bridge missing scores.
        result.append(row)
    return result


def risk_metrics(records, transition_sequence=None, tolerance=TOLERANCE):
    if isinstance(tolerance, bool) or not isinstance(tolerance, (float,int)) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be finite and nonnegative')
    if transition_sequence is not None and (type(transition_sequence) is not int or transition_sequence < 1):
        raise ValueError('transition_sequence must be a positive integer')
    rows = with_risk_deltas(records)
    sequences = [r['sequence_number'] for r in rows]
    if any(type(n) is not int or n < 1 for n in sequences) or sequences != sorted(set(sequences)):
        raise ValueError('Records must have unique increasing positive sequences')
    values = [r['risk_score'] for r in rows if r['risk_score'] is not None]
    groups = defaultdict(list)
    for r in rows: groups[comparison_key(r)].append(r)
    initial = mean([g[0]['risk_score'] for g in groups.values() if g[0]['risk_score'] is not None])
    final = mean([g[-1]['risk_score'] for g in groups.values() if g[-1]['risk_score'] is not None])
    paired = [g for g in groups.values() if g[0]['risk_score'] is not None and g[-1]['risk_score'] is not None]
    # Use the same cohort for endpoints, avoiding composition changes from nulls.
    initial = mean([g[0]['risk_score'] for g in paired])
    final = mean([g[-1]['risk_score'] for g in paired])
    pre = [] if transition_sequence is None else [r for r in rows if r['sequence_number'] < transition_sequence]
    post = [] if transition_sequence is None else [r for r in rows if r['sequence_number'] >= transition_sequence]
    def average(part, field):
        return mean([r[field] for r in part if r[field] is not None])
    before, after = average(pre,'risk_score'), average(post,'risk_score')
    eligible = [r for r in rows if r['risk_delta'] is not None]
    benign = [r for r in eligible if r['ground_truth']=='BENIGN']
    malicious = [r for r in eligible if r['ground_truth']=='MALICIOUS']
    positive = lambda r: r['risk_delta'] > tolerance
    observed = next((r for r in post if r['risk_delta'] is not None and positive(r)), None)
    delay = {'status': 'NOT_APPLICABLE' if transition_sequence is None else 'OBSERVED' if observed else 'NOT_OBSERVED',
             'sequence_delay': observed['sequence_number']-transition_sequence if observed else None}
    contributions = {}
    for component in COMPONENTS:
        def cm(part):
            return mean([r['component_contributions'][component] for r in part if r['component_contributions'][component] is not None])
        p,q = cm(pre),cm(post)
        contributions[component] = {'mean':cm(rows),'pre_mean':p,'post_mean':q,
            'transition_change':q-p if p is not None and q is not None else None,
            'mean_share':mean([r['component_contributions'][component]/r['risk_score'] for r in rows
                              if r['risk_score'] is not None and r['risk_score'] > 0 and r['component_contributions'][component] is not None])}
    at = next((r for r in rows if r['sequence_number']==transition_sequence),None)
    prior = next((r for r in rows if transition_sequence is not None and r['sequence_number']==transition_sequence-1),None)
    coverages = [r['coverage'] for r in rows]
    pre_benign = [r for r in pre if r['ground_truth']=='BENIGN' and r['risk_delta'] is not None]
    return {'observation_count':len(rows),'defined_risk_count':len(values),'null_risk_count':len(rows)-len(values),
        'comparison_group_count':len(groups),'endpoint_group_count':len(paired),
        'initial_risk':initial,'final_risk':final,'net_risk_change':final-initial if initial is not None and final is not None else None,
        'minimum_risk':min(values) if values else None,'maximum_risk':max(values) if values else None,'mean_risk':mean(values),
        'eligible_update_count':len(eligible),'mean_absolute_risk_update':mean([abs(r['risk_delta']) for r in eligible]),
        'pre_mean_risk':before,'post_mean_risk':after,'signed_risk_escalation':after-before if before is not None and after is not None else None,
        'risk_before_transition':prior['risk_score'] if prior else None,'risk_at_transition':at['risk_score'] if at else None,
        'transition_risk_delta':at['risk_delta'] if at else None,'risk_response_delay':delay,
        'eligible_benign_count':len(benign),'false_escalation_count':sum(map(positive,benign)),
        'false_escalation_rate':ratio(sum(map(positive,benign)),len(benign)),
        'eligible_malicious_count':len(malicious),'positive_risk_response_count':sum(map(positive,malicious)),
        'positive_risk_response_rate':ratio(sum(map(positive,malicious)),len(malicious)),
        'pre_benign_false_escalation_rate':ratio(sum(map(positive,pre_benign)),len(pre_benign)),
        'mean_coverage':mean(coverages),'min_coverage':min(coverages) if coverages else None,'max_coverage':max(coverages) if coverages else None,
        'availability_rates':{k:ratio(sum(r['component_availability'][k]=='AVAILABLE' for r in rows),len(rows)) for k in COMPONENTS},
        'contributions':contributions}


def aggregate_runs(runs):
    grouped = defaultdict(list)
    for run in runs: grouped[run['experiment']['scenario_id']].append(run['metrics'])
    def numeric_tree(items):
        result = {}
        for key,value in items[0].items():
            values = [item[key] for item in items]
            if isinstance(value,dict): result[key] = numeric_tree(values)
            elif value is None or type(value) in (int,float): result[key] = summarize(values)
        return result
    result = {}
    for scenario,metrics in sorted(grouped.items()):
        result[scenario] = numeric_tree(metrics)
        result[scenario]['run_count'] = len(metrics)
        result[scenario]['positive_escalation_runs'] = sum(m['signed_risk_escalation'] is not None and m['signed_risk_escalation']>TOLERANCE for m in metrics)
        result[scenario]['positive_transition_runs'] = sum(m['transition_risk_delta'] is not None and m['transition_risk_delta']>TOLERANCE for m in metrics)
        result[scenario]['runs_with_false_escalation'] = sum(m['false_escalation_count']>0 for m in metrics)
        result[scenario]['delay_status_counts'] = {s:sum(m['risk_response_delay']['status']==s for m in metrics) for s in ('OBSERVED','NOT_OBSERVED','NOT_APPLICABLE')}
    return result
