"""Offline metrics only: this module may read evaluation labels."""
from collections import defaultdict
from statistics import fmean, pstdev
from core.trust_evidence import TrustDimension


def mean(values):
    return fmean(values) if values else None


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(values):
    valid = [v for v in values if v is not None]
    return {'defined_runs': len(valid), 'missing_runs': len(values)-len(valid),
            'mean': mean(valid), 'standard_deviation': pstdev(valid) if valid else None,
            'minimum': min(valid) if valid else None, 'maximum': max(valid) if valid else None}


def trust_metrics(records, intervention_sequence=None):
    """Input order is experimental order. Deltas always belong to their own entity."""
    records = list(records)
    if intervention_sequence is not None and (type(intervention_sequence) is not int or intervention_sequence < 1):
        raise ValueError('intervention_sequence must be a positive integer or None')
    grouped = defaultdict(list)
    for row in records:
        grouped[row['entity_id']].append(row)
    values = [r['composite_trust'] for r in records]
    initial = mean([rows[0]['previous_composite_trust'] for rows in grouped.values()])
    final = mean([rows[-1]['composite_trust'] for rows in grouped.values()])
    benign = [r for r in records if r['ground_truth'] == 'BENIGN']
    malicious = [r for r in records if r['ground_truth'] == 'MALICIOUS']
    false = sum(r['trust_delta'] < 0 for r in benign)
    responses = sum(r['trust_delta'] < 0 for r in malicious)
    pre = [] if intervention_sequence is None else [r for r in records if r['sequence_number'] < intervention_sequence]
    post = [] if intervention_sequence is None else [r for r in records if r['sequence_number'] >= intervention_sequence]
    before_values, at_values, final_post = [], [], []
    for rows in grouped.values():
        before = [] if intervention_sequence is None else [r for r in rows if r['sequence_number'] < intervention_sequence]
        after = [] if intervention_sequence is None else [r for r in rows if r['sequence_number'] >= intervention_sequence]
        if before and after:
            before_values.append(before[-1]['composite_trust'])
            at_values.append(after[0]['composite_trust'])
            final_post.append(after[-1]['composite_trust'])
    reference, end = mean(before_values), mean(final_post)
    decreases = [r for r in post if r['trust_delta'] < 0]
    if intervention_sequence is None:
        delay = {'status':'NOT_APPLICABLE', 'sequence_delay':None, 'entity_observation_delay':None}
    elif not decreases:
        delay = {'status':'NOT_OBSERVED', 'sequence_delay':None, 'entity_observation_delay':None}
    else:
        first = min(decreases, key=lambda r:r['sequence_number'])
        local_post = [r for r in post if r['entity_id'] == first['entity_id']]
        delay = {'status':'OBSERVED', 'sequence_delay':first['sequence_number']-intervention_sequence,
                 'entity_observation_delay':next(i for i,r in enumerate(local_post) if r is first)}
    coverage = {}
    for dimension in TrustDimension:
        name = dimension.value
        counts = {sign:sum(sign in r['evidence_coverage'][name] for r in records) for sign in ('POSITIVE','NEGATIVE','INSUFFICIENT')}
        counts['NEUTRAL'] = sum(any(e['dimension']==name and e['direction']=='NEUTRAL' for e in r['evidence']) for r in records)
        coverage[name] = {sign:{'count':count,'rate':ratio(count,len(records))} for sign,count in counts.items()}
    return {'observation_count':len(records), 'entity_count':len(grouped),
            'initial_trust':initial, 'final_trust':final,
            'minimum_trust':min(values) if values else None,'maximum_trust':max(values) if values else None,
            'mean_trust':mean(values), 'trust_change':final-initial if values else None,
            'pre_intervention_mean':mean([r['composite_trust'] for r in pre]),
            'post_intervention_mean':mean([r['composite_trust'] for r in post]),
            'pre_intervention_reference':reference, 'first_post_intervention_trust':mean(at_values),
            'degradation_magnitude':reference-end if reference is not None else None,
            'degradation_delay':delay,
            'benign_observations':len(benign),'false_degradation_count':false,'false_degradation_rate':ratio(false,len(benign)),
            'malicious_observations':len(malicious),'negative_response_count':responses,'negative_response_rate':ratio(responses,len(malicious)),
            'malicious_without_direct_negative_evidence':sum(r['negative_evidence_count']==0 for r in malicious),
            'volatility_mean_absolute_update':mean([abs(r['trust_delta']) for r in records]),
            'evidence_coverage':coverage,
            'recovery':{'status':'NOT_MEASURABLE_WITH_CURRENT_SCENARIOS','delay':None}}


def aggregate_runs(runs):
    grouped = defaultdict(list)
    for run in runs: grouped[run['experiment']['scenario_id']].append(run['metrics'])
    result = {}
    for scenario, metrics in sorted(grouped.items()):
        names = [name for name,value in metrics[0].items() if value is None or type(value) in (int,float)]
        result[scenario] = {name:summarize([m[name] for m in metrics]) for name in names}
        result[scenario]['degradation_sequence_delay'] = summarize([m['degradation_delay']['sequence_delay'] for m in metrics])
        result[scenario]['degradation_not_observed_runs'] = sum(m['degradation_delay']['status']=='NOT_OBSERVED' for m in metrics)
        result[scenario]['evidence_coverage_rates'] = {
            dim:{sign:summarize([m['evidence_coverage'][dim][sign]['rate'] for m in metrics])
                 for sign in ('POSITIVE','NEGATIVE','NEUTRAL','INSUFFICIENT')}
            for dim in metrics[0]['evidence_coverage']}
    return result
