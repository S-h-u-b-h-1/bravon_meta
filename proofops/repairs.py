"""Closed, auditable action allowlist. No model-generated commands are executed."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .domain import LabConfig


@dataclass(frozen=True)
class RepairAction:
    id: str
    label: str
    description: str
    apply: Callable[[LabConfig], None]


def _restore_dns(config: LabConfig) -> None:
    config.dns_record = "edge-proxy"


def _restore_proxy(config: LabConfig) -> None:
    config.proxy_upstream = "backend-a"


def _failover(config: LabConfig) -> None:
    if not config.backend_b_running:
        raise ValueError("Standby is not healthy; cannot fail over")
    config.proxy_upstream = "backend-b"


ACTIONS: dict[str, RepairAction] = {
    "restore_dns": RepairAction("restore_dns", "Restore DNS mapping", "Change lab DNS record back to edge-proxy", _restore_dns),
    "restore_proxy": RepairAction("restore_proxy", "Restore proxy route", "Set lab gateway upstream to backend-a", _restore_proxy),
    "failover": RepairAction("failover", "Fail over to Backend B", "Route lab traffic to healthy standby backend", _failover),
}


def safe_action(action_id: str, config: LabConfig) -> LabConfig:
    """Execute a known action on a clone ONLY; callers must explicitly store result."""
    if action_id not in ACTIONS:
        raise ValueError("Unrecognized repair action")
    next_config = config.clone()
    ACTIONS[action_id].apply(next_config)
    return next_config
