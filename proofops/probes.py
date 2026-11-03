"""Deterministic checks over an explicitly simulated topology.

The probes model relevant DNS / proxy / backend invariants; they are NOT
observations of the host OS, a real DNS server, or a production application.
"""
from __future__ import annotations

from .domain import Check, LabConfig


def check_all(config: LabConfig) -> list[Check]:
    dns_ok = config.dns_record == "edge-proxy"
    upstream_valid = config.proxy_upstream in ("backend-a", "backend-b")
    selected_running = {
        "backend-a": config.backend_a_running,
        "backend-b": config.backend_b_running,
    }.get(config.proxy_upstream, False)
    end_to_end = dns_ok and upstream_valid and selected_running

    return [
        Check(
            "dns-record", "DNS resolution", dns_ok,
            config.dns_record, "edge-proxy",
            "Internal lab DNS record must lead to the edge proxy.",
        ),
        Check(
            "proxy-route", "Proxy upstream", upstream_valid,
            config.proxy_upstream, "backend-a or backend-b",
            "Gateway should route to a declared backend.",
        ),
        Check(
            "upstream-health", "Selected backend", bool(selected_running),
            "ready" if selected_running else "unavailable", "ready",
            "The backend selected by the proxy must be running.",
        ),
        Check(
            "e2e", "End-to-end request", end_to_end,
            "HTTP 200" if end_to_end else "HTTP 503 (simulated)", "HTTP 200",
            "Synthetic client → DNS → proxy → backend request path.",
        ),
        Check(
            "standby", "Standby backend", config.backend_b_running,
            "ready" if config.backend_b_running else "unavailable", "ready",
            "Ensures the failover target is alive.",
        ),
    ]


def is_healthy(checks: list[Check]) -> bool:
    return all(check.passed for check in checks)


def components(config: LabConfig) -> list[dict]:
    """Topology state for the UI, independent of agent claims."""
    return [
        {"id": "client", "name": "Client", "role": "Synthetic request", "health": "healthy", "detail": "GET /"},
        {"id": "dns", "name": "DNS resolver", "role": "app.proofops.test", "health": "healthy" if config.dns_record == "edge-proxy" else "critical", "detail": config.dns_record},
        {"id": "proxy", "name": "Edge proxy", "role": "Gateway routing", "health": "healthy" if config.proxy_upstream in ("backend-a", "backend-b") else "critical", "detail": config.proxy_upstream},
        {"id": "backend-a", "name": "Backend A", "role": "Primary service", "health": "healthy" if config.backend_a_running else "critical", "detail": "Online" if config.backend_a_running else "Stopped"},
        {"id": "backend-b", "name": "Backend B", "role": "Standby service", "health": "healthy" if config.backend_b_running else "critical", "detail": "Online" if config.backend_b_running else "Stopped"},
    ]
