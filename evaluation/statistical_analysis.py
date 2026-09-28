"""Seed-level descriptive and paired analyses; events are never replication units."""
import math


def summary(values):
    values = [value for value in values if value is not None]; n = len(values)
    if not values:
        return {'n_seeds': 0, 'reason': 'NOT_APPLICABLE: no eligible denominator.'}
    mean = sum(values) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1)) if n > 1 else 0.0
    return {'n_seeds': n, 'mean': mean, 'sample_sd': sd, 'median': sorted(values)[n // 2],
            'min': min(values), 'max': max(values), 'ci95': [mean - 1.96 * sd / math.sqrt(n), mean + 1.96 * sd / math.sqrt(n)]}


def paired_difference(left, right):
    diffs = [a - b for a, b in zip(left, right)]
    result = summary(diffs)
    if result['sample_sd'] == 0:
        result.update(effect_size={'value': None, 'reason': 'NOT_APPLICABLE: zero variance paired differences.'},
                      test={'name': 'NOT_APPLICABLE', 'reason': 'constant differences; no inferential test reported.'})
    else:
        result.update(effect_size={'method': 'paired Cohen dz', 'value': result['mean'] / result['sample_sd']},
                      test={'name': 'NOT_REPORTED', 'reason': 'Exploratory five/20-seed reporting; no p-value claim.'})
    return result
