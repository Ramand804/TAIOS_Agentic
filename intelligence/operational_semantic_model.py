"""Deterministic semantics over the allowlisted observable request."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
import math

import yaml

from core.experiment import fingerprint
from core.operational_semantics import OperationalSemanticAssessment, SemanticStatus
from core.runtime_inputs import OBSERVABLE_FIELDS
from environment.operational_limits import OperationalLimits

SEMANTIC_POLICY_VERSION = 'milestone6a-operational-semantics-v1'


@dataclass(frozen=True)
class SemanticRule:
    rule_id: str
    operation: str
    target_types: tuple[str, ...]
    value_type: str
    required_observable_fields: tuple[str, ...]
    constraint_source: str

    def to_dict(self):
        return {
            'rule_id': self.rule_id, 'operation': self.operation,
            'target_types': list(self.target_types), 'value_type': self.value_type,
            'required_observable_fields': list(self.required_observable_fields),
            'constraint_source': self.constraint_source,
        }


class OperationalSemanticRegistry:
    def __init__(self, path=None):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'operational_semantics.yaml')
        with path.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict) or set(data) != {'version', 'operations'}:
            raise ValueError('Invalid operational semantic registry schema')
        if data['version'] != SEMANTIC_POLICY_VERSION or not isinstance(data['operations'], dict):
            raise ValueError('Unsupported operational semantic registry version')
        rules = {}
        required = {'target_types', 'value_type', 'required_observable_fields', 'constraint_source'}
        for operation, row in data['operations'].items():
            if not isinstance(row, dict) or set(row) != required:
                raise ValueError('Invalid semantic rule schema')
            rule = SemanticRule(
                rule_id=f'OPS-{operation.upper()}', operation=operation,
                target_types=tuple(row['target_types']), value_type=row['value_type'],
                required_observable_fields=tuple(row['required_observable_fields']),
                constraint_source=row['constraint_source'])
            rules[operation] = rule
        self.version = data['version']
        self.rules = MappingProxyType(rules)

    def to_dict(self):
        return {'version': self.version,
                'operations': {key: self.rules[key].to_dict() for key in sorted(self.rules)}}

    @property
    def fingerprint(self):
        return fingerprint(self.to_dict())


class OperationalSemanticModel:
    def __init__(self, registry=None, operational_limits=None):
        self.registry = OperationalSemanticRegistry() if registry is None else registry
        self.operational_limits = OperationalLimits() if operational_limits is None else operational_limits
        if type(self.registry) is not OperationalSemanticRegistry:
            raise ValueError('Expected OperationalSemanticRegistry')
        if type(self.operational_limits) is not OperationalLimits:
            raise ValueError('Expected OperationalLimits')

    @staticmethod
    def _validate(observation):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection')

    def assess(self, observation):
        self._validate(observation)
        operation = observation['operation']
        rule = self.registry.rules.get(operation)
        common = dict(
            source_id=observation['source_id'], target_id=observation['target_id'],
            target_type=observation['target_type'], operation=operation,
            observed_value=observation['requested_value'],
            semantic_policy_version=self.registry.version,
            semantic_policy_fingerprint=self.registry.fingerprint)
        if rule is None or observation['target_type'] not in rule.target_types:
            reason = ('Operation has no declared semantic rule.' if rule is None else
                      'Operation is not declared for the observable target type.')
            return OperationalSemanticAssessment(
                **common, semantic_status=SemanticStatus.UNSUPPORTED,
                value_semantics_status='UNKNOWN', operational_validity='UNKNOWN',
                known_constraints={}, applicable_semantic_rule_ids=(),
                unresolved_semantic_requirements=('A declared operation/target semantic rule is required.',),
                reasons=(reason,))

        context = observation['contextual_features']
        missing = tuple(field for field in rule.required_observable_fields if
                        (field == 'operating_mode' and field not in context) or
                        (field != 'operating_mode' and field not in observation))
        if operation == 'write_register':
            return OperationalSemanticAssessment(
                **common, semantic_status=SemanticStatus.UNDERSPECIFIED,
                value_semantics_status='REGISTER_VALUE_UNRESOLVED',
                operational_validity='UNKNOWN',
                known_constraints={
                    'recognized_operation': True, 'value_type': rule.value_type,
                    'required_observable_fields': rule.required_observable_fields,
                    'constraint_source': rule.constraint_source},
                applicable_semantic_rule_ids=(rule.rule_id,),
                unresolved_semantic_requirements=(
                    'Observable register_address is required.',
                    'Register-specific data type and allowed value/domain are required.'),
                reasons=('write_register is recognized, but the runtime schema does not identify the register; '
                         'the observed value cannot be validated safely.',))
        if missing:
            return OperationalSemanticAssessment(
                **common, semantic_status=SemanticStatus.UNDERSPECIFIED,
                value_semantics_status='VALUE_TYPE_KNOWN_CONTEXT_MISSING',
                operational_validity='UNKNOWN',
                known_constraints={'value_type': rule.value_type,
                                   'constraint_source': rule.constraint_source},
                applicable_semantic_rule_ids=(rule.rule_id,),
                unresolved_semantic_requirements=tuple(
                    f'Observable {field} is required.' for field in missing),
                reasons=('Recognized operation lacks required observable context.',))
        value = observation['requested_value']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return OperationalSemanticAssessment(
                **common, semantic_status=SemanticStatus.SUPPORTED_INVALID,
                value_semantics_status='INVALID_NUMERIC_VALUE', operational_validity='INVALID',
                known_constraints={'value_type': rule.value_type},
                applicable_semantic_rule_ids=(rule.rule_id,),
                unresolved_semantic_requirements=(),
                reasons=('set_speed requires a finite numeric value.',))
        mode = context['operating_mode']
        try:
            check = self.operational_limits.check_operational_limit(
                observation['target_id'], operation, value, mode)
        except KeyError:
            return OperationalSemanticAssessment(
                **common, semantic_status=SemanticStatus.UNSUPPORTED,
                value_semantics_status='NUMERIC', operational_validity='UNKNOWN',
                known_constraints={'constraint_source': rule.constraint_source},
                applicable_semantic_rule_ids=(rule.rule_id,),
                unresolved_semantic_requirements=(
                    'A canonical target/operation/mode limit is required.',),
                reasons=('No canonical operational limit exists for this target and mode.',))
        valid = check.within_limit
        return OperationalSemanticAssessment(
            **common, semantic_status=(SemanticStatus.SUPPORTED_VALID if valid
                                       else SemanticStatus.SUPPORTED_INVALID),
            value_semantics_status='NUMERIC',
            operational_validity='WITHIN_LIMIT' if valid else 'OUTSIDE_LIMIT',
            known_constraints={'minimum': check.minimum, 'maximum': check.maximum,
                               'operating_mode': mode, 'inclusive': True,
                               'constraint_source': rule.constraint_source},
            applicable_semantic_rule_ids=(rule.rule_id,),
            unresolved_semantic_requirements=(),
            reasons=((f'set_speed value {value} is within inclusive [{check.minimum}, {check.maximum}] '
                      f'for {mode}.') if valid else
                     (f'set_speed value {value} is outside inclusive [{check.minimum}, {check.maximum}] '
                      f'for {mode}.'),))
