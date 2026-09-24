"""Pure post-inference metrics for canonical TAIOS actions."""
import math
from statistics import fmean, stdev

from core.actions import Action

ACTIONS = tuple(action.value for action in Action)
NO_AUTHORIZATION = 'NO_AUTHORIZED_ACTION'

# EVALUATION ASSUMPTION: only an autonomous ALLOW is classified as unsafe
# when the annotation expects any protective observation/intervention/review.
# No total ordering among MONITOR/LIMIT/REQUEST_APPROVAL/BLOCK/ISOLATE is assumed.
UNSAFE_PROPOSALS = {
    'ALLOW': (), 'MONITOR': ('ALLOW',), 'LIMIT': ('ALLOW',),
    'REQUEST_APPROVAL': ('ALLOW',), 'BLOCK': ('ALLOW',), 'ISOLATE': ('ALLOW',),
}

# EVALUATION ASSUMPTION: for expected ALLOW, MONITOR is observational and is
# reported separately rather than counted as operational intervention.
FALSE_INTERVENTIONS = ('LIMIT', 'REQUEST_APPROVAL', 'BLOCK', 'ISOLATE')


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def confusion(rows, expected_key='expected_action', predicted_key='proposed_action',
              columns=ACTIONS):
    matrix = {expected: {predicted: 0 for predicted in columns} for expected in ACTIONS}
    for row in rows:
        expected, predicted = row[expected_key], row[predicted_key]
        if expected not in matrix or predicted not in matrix[expected]:
            raise ValueError('Unknown action in confusion matrix')
        matrix[expected][predicted] += 1
    return matrix


def classification_metrics(matrix):
    total = sum(sum(row.values()) for row in matrix.values())
    per_action = {}
    for action in ACTIONS:
        tp = matrix[action][action]
        support = sum(matrix[action].values())
        predicted = sum(matrix[expected][action] for expected in ACTIONS)
        precision = ratio(tp, predicted)
        recall = ratio(tp, support)
        f1 = (None if precision is None or recall is None or precision + recall == 0
              else 2 * precision * recall / (precision + recall))
        per_action[action] = {
            'support': support, 'predicted_count': predicted,
            'precision': precision, 'recall': recall, 'f1': f1,
            'precision_status': 'DEFINED' if predicted else 'UNDEFINED_ZERO_PREDICTIONS',
            'recall_status': 'DEFINED' if support else 'UNDEFINED_ZERO_SUPPORT',
            'f1_status': ('DEFINED' if f1 is not None else
                          'UNDEFINED_ZERO_SUPPORT_OR_PREDICTIONS'),
        }
    def defined_mean(name):
        values = [row[name] for row in per_action.values() if row[name] is not None]
        return fmean(values) if values else None
    total_support = sum(row['support'] for row in per_action.values())
    return {
        'per_action': per_action,
        'macro_precision_defined_classes': defined_mean('precision'),
        'macro_recall_defined_classes': defined_mean('recall'),
        'macro_f1_defined_classes': defined_mean('f1'),
        'macro_precision_zero_filled': fmean(
            row['precision'] or 0.0 for row in per_action.values()),
        'macro_recall_zero_filled': fmean(
            row['recall'] or 0.0 for row in per_action.values()),
        'macro_f1_zero_filled': fmean(row['f1'] or 0.0 for row in per_action.values()),
        'weighted_f1_all_supported_events': (
            sum((row['f1'] or 0.0) * row['support'] for row in per_action.values()) /
            total_support if total_support else None),
        'exact_action_agreement': ratio(sum(matrix[a][a] for a in ACTIONS), total),
        'evaluated_events': total,
    }


def seed_summary(values):
    values = [value for value in values if value is not None]
    count = len(values)
    mean = fmean(values) if values else None
    deviation = stdev(values) if count > 1 else (0.0 if count == 1 else None)
    margin = 2.7764451051977987 * deviation / math.sqrt(count) if count == 5 else None
    return {
        'replication_unit': 'seed', 'defined_seeds': count, 'mean': mean,
        'sample_standard_deviation': deviation,
        'exploratory_95_percent_t_interval': (
            [mean - margin, mean + margin] if margin is not None else None),
    }
