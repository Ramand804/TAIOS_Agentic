"""Immutable Milestone-8A experimental configuration definitions."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, texts
from core.experiment import fingerprint
from core.risk_input import text_value


class ExperimentalConfiguration(str, Enum):
    RULE_BASED = 'RULE_BASED'
    TAIOS_STATIC = 'TAIOS_STATIC'
    TAIOS_ADAPTIVE = 'TAIOS_ADAPTIVE'
    TAIOS_NO_TRUST = 'TAIOS_NO_TRUST'


@dataclass(frozen=True, kw_only=True)
class ExperimentalConfigurationSpec(Record):
    configuration: ExperimentalConfiguration
    version: str
    differing_components: tuple[str, ...]
    shared_components: tuple[str, ...]
    rationale: str

    def __post_init__(self):
        object.__setattr__(self, 'configuration', ExperimentalConfiguration(self.configuration))
        text_value(self.version, 'version')
        text_value(self.rationale, 'rationale')
        object.__setattr__(self, 'differing_components', texts(self.differing_components))
        object.__setattr__(self, 'shared_components', texts(self.shared_components))

    @property
    def configuration_fingerprint(self):
        return fingerprint(self.to_dict())
