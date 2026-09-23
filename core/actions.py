"""Canonical action type for new decision contracts; frozen labels unchanged."""
from enum import Enum


class Action(str, Enum):
    ALLOW = 'ALLOW'
    MONITOR = 'MONITOR'
    LIMIT = 'LIMIT'
    REQUEST_APPROVAL = 'REQUEST_APPROVAL'
    BLOCK = 'BLOCK'
    ISOLATE = 'ISOLATE'
