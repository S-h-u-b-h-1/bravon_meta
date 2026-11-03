"""ProofOps v0.3: real, *disposable* Docker incident laboratory.

No model can execute commands. The controller issues a fixed set of Compose commands
against randomly named, internally networked project stacks. The verification stack
runs separately and is deleted before operator-authorized application to active.

Run as a CLI or enable the separate localhost web panel explicitly. Do not expose
this unauthenticated developer laboratory to the Internet.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from threading import RLock
from time import monotonic, sleep
from typing import Any


APP_HOST = "app.proofops.test"
CONFIRM_PHRASE = "APPLY TO LOCAL DOCKER LAB"
CLOUD_CONSENT_PHRASE = "SEND DISPOSABLE LAB PROBE DATA TO OPENROUTER"
HOSTED_MUSE_CONSENT_PHRASE = "SEND DISPOSABLE LAB PROBE DATA TO HOSTED MUSE"
SCENARIOS = {
    "dns-drift": "DNS record drift",
    "proxy-misroute": "Nginx upstream misroute",
    "backend-outage": "Backend A process stopped",
}
ACTIONS = {"restore_dns", "restore_proxy", "failover"}
RELOAD_WAIT_SECONDS = 1.25


class DockerLabError(RuntimeError):
    pass


class LabConflict(DockerLabError):
    pass


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str


class CommandRunner:
    """Only invoke Docker's CLI with an array; no shell or user supplied args."""

    def run(self, argv: list[str], env: dict[str, str], cwd: Path, timeout: float) -> CommandResult:
        try:
            result = subprocess.run(
                argv, cwd=cwd, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout, check=False,
            )
        except FileNotFoundError as exc:
            raise DockerLabError("Docker CLI not found. Install and start Docker Desktop.") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerLabError("A Docker command timed out; inspect the lab before retrying.") from exc
        # Prevent huge container logs in memory/HTTP responses.
        return CommandResult(result.returncode, result.stdout[-16000:], result.stderr[-8000:])


class ComposeStack:
    def __init__(self, root: Path, project: str, slot: int, runner: CommandRunner):
        if not re.fullmatch(r"proofops-[a-z0-9-]{4,55}", project):
            raise ValueError("Invalid internally generated Docker Compose project name")
        if not 20 <= slot <= 220:
            raise ValueError("Network slot must be in the range 20..220")
        self.project = project
        self.slot = slot
        self.root = root
        self.runner = runner
        self.stack_dir = root / project
        self.compose_file = Path(__file__).resolve().parents[1] / "infra" / "compose.yaml"
        self.prefix = f"10.223.{slot}"
        self.edge_ip = self.ip(10)
        self.dns_ip = self.ip(53)
        self.backend_a_ip = self.ip(21)
        self.backend_b_ip = self.ip(22)
        self.probe_ip = self.ip(30)
        self.wrong_ip = self.ip(99)
        # Compose only needs Docker/OS environment, never unrelated AI credentials.
        # Do not forward locally exported provider keys into subprocess environments.
        safe_env = {key: value for key, value in os.environ.items()
                    if not any(marker in key.upper() for marker in
                               ("API_KEY", "_TOKEN", "_SECRET", "PASSWORD", "DOCKER_AUTH_CONFIG"))}
        self.env = {
            **safe_env,
            "PROOFOPS_STACK_DIR": str(self.stack_dir),
            "PROOFOPS_SUBNET": f"{self.prefix}.0/24",
            "PROOFOPS_DNS_IP": self.dns_ip,
            "PROOFOPS_EDGE_IP": self.edge_ip,
            "PROOFOPS_BACKEND_A_IP": self.backend_a_ip,
            "PROOFOPS_BACKEND_B_IP": self.backend_b_ip,
            "PROOFOPS_PROBE_IP": self.probe_ip,
        }

    def ip(self, end: int) -> str:
        return str(ipaddress.IPv4Address(f"{self.prefix}.{end}"))

    def run(self, *args: str, timeout: float = 30.0, strict: bool = True) -> CommandResult:
        # All arguments in callers are fixed constants or internally derived IDs.
        argv = ["docker", "compose", "-f", str(self.compose_file), "-p", self.project, *args]
        result = self.runner.run(argv, self.env, self.compose_file.parent, timeout)
        if strict and result.code:
            detail = (result.stderr or result.stdout).strip()[-800:]
            raise DockerLabError(f"Docker Compose {args[0]} failed (exit {result.code}): {detail}")
        return result

    def init_files(self, config: dict[str, Any]) -> None:
        (self.stack_dir / "dns").mkdir(parents=True, exist_ok=True)
        (self.stack_dir / "nginx").mkdir(parents=True, exist_ok=True)
        self.write_config(config)

    def write_config(self, config: dict[str, Any]) -> None:
        dns = self.edge_ip if config["dns_target"] == "edge" else self.wrong_ip
        upstream = {"backend-a": self.backend_a_ip, "backend-b": self.backend_b_ip,
                    "bogus": self.wrong_ip}[config["proxy_target"]]
        # Mount directories, not individual files: atomic renames remain visible to Docker Desktop.
        _atomic_text(self.stack_dir / "dns" / "hosts", f"{dns} {APP_HOST}\n")
        nginx = ("server {\n"
                 "    listen 8080;\n"
                 "    server_name _;\n"
                 "    access_log /dev/stdout;\n"
                 "    error_log /dev/stderr warn;\n"
                 "    proxy_connect_timeout 2s;\n"
                 "    proxy_read_timeout 2s;\n"
                 "    location / {\n"
                 f"        proxy_pass http://{upstream}:8080;\n"
                 "        proxy_set_header Host $host;\n"
                 "    }\n"
                 "}\n")
        _atomic_text(self.stack_dir / "nginx" / "default.conf", nginx)

    def reload_edge(self) -> None:
        self.run("exec", "-T", "edge", "nginx", "-t", timeout=15)
        self.run("exec", "-T", "edge", "nginx", "-s", "reload", timeout=15)

    def set_dns(self, target: str) -> None:
        current = _read_file(self.stack_dir / "dns" / "hosts")
        parsed_ip = self.edge_ip if target == "edge" else self.wrong_ip
        _atomic_text(self.stack_dir / "dns" / "hosts", f"{parsed_ip} {APP_HOST}\n")
        if current == "":
            raise DockerLabError("DNS hosts file not initialized")
        # CoreDNS hosts plugin reloads on its own; the observer checks effective DNS.

    def set_proxy(self, target: str) -> None:
        old = _read_file(self.stack_dir / "nginx" / "default.conf")
        upstream = {"backend-a": self.backend_a_ip, "backend-b": self.backend_b_ip,
                    "bogus": self.wrong_ip}[target]
        replacement = re.sub(r"proxy_pass http://\d+\.\d+\.\d+\.\d+:8080;",
                             f"proxy_pass http://{upstream}:8080;", old)
        if replacement == old:
            raise DockerLabError("Expected Nginx upstream directive is missing")
        _atomic_text(self.stack_dir / "nginx" / "default.conf", replacement)
        try:
            self.reload_edge()
        except Exception:
            _atomic_text(self.stack_dir / "nginx" / "default.conf", old)
            self.reload_edge()
            raise

    def set_backend_a(self, running: bool) -> None:
        self.run("start" if running else "stop", "backend-a", timeout=30)

    def inspect(self) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        query = self.run("exec", "-T", "probe", "nslookup", APP_HOST, self.dns_ip,
                         strict=False, timeout=10)
        addresses = re.findall(r"Address(?:\s+\d+)?:\s*(\d{1,3}(?:\.\d{1,3}){3})",
                               query.stdout)
        dns_found = next((ip for ip in reversed(addresses) if ip != self.dns_ip), "unresolved")
        checks.append(_check("dns-record", "Real DNS answer", query.code == 0 and
                             dns_found == self.edge_ip, dns_found, self.edge_ip,
                             "CoreDNS queried by the isolated probe container"))

        actual = self.run("exec", "-T", "edge", "nginx", "-T", strict=False, timeout=12)
        combined = actual.stdout + "\n" + actual.stderr
        matches = re.findall(r"\bproxy_pass\s+http://(\d{1,3}(?:\.\d{1,3}){3}):8080\s*;", combined)
        route = matches[-1] if matches else "unknown"
        allowed = {self.backend_a_ip: "backend-a", self.backend_b_ip: "backend-b"}
        checks.append(_check("proxy-route", "Nginx route", actual.code == 0 and
                             route in allowed, route, "a declared backend IP",
                             "nginx -T from the running edge container"))

        selected = allowed.get(route)
        selected_response = self._http(f"http://{route}:8080/health") if selected else None
        selected_ok = bool(selected and selected_response and selected_response.get("status") == "ok"
                           and selected_response.get("backend") == selected)
        checks.append(_check("upstream-health", "Selected backend HTTP", selected_ok,
                             selected if selected_ok else "unreachable",
                             "HTTP 200 with matching backend identity",
                             "Direct HTTP probe from the isolated client container"))

        e2e_response = self._http(f"http://{APP_HOST}:8080/health")
        e2e_ok = bool(e2e_response and e2e_response.get("status") == "ok" and
                      e2e_response.get("backend") == selected and selected in allowed.values() and
                      dns_found == self.edge_ip)
        checks.append(_check("e2e", "Client → DNS → Nginx → backend", e2e_ok,
                             (e2e_response or {}).get("backend", "request failed"),
                             "HTTP 200 via app.proofops.test",
                             "End-to-end HTTP through real DNS and edge containers"))

        standby = self._http(f"http://{self.backend_b_ip}:8080/health")
        standby_ok = bool(standby and standby.get("status") == "ok" and
                          standby.get("backend") == "backend-b")
        checks.append(_check("standby", "Standby backend HTTP", standby_ok,
                             "ready" if standby_ok else "unavailable", "ready",
                             "Direct HTTP probe of independent standby"))
        return checks

    def _http(self, url: str) -> dict[str, Any] | None:
        result = self.run("exec", "-T", "probe", "wget", "-q", "-T", "3", "-O", "-", url,
                          timeout=9, strict=False)
        if result.code:
            return None
        try:
            body = json.loads(result.stdout)
            return body if isinstance(body, dict) else None
        except json.JSONDecodeError:
            return None

    def fingerprint(self, checks: list[dict[str, Any]]) -> str:
        payload = {
            "dns_file": _read_file(self.stack_dir / "dns" / "hosts"),
            "nginx_file": _read_file(self.stack_dir / "nginx" / "default.conf"),
            "checks": [(c["id"], c["passed"], c["observed"]) for c in checks],
        }
        return _digest(payload)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise DockerLabError("Symlink paths are not allowed in the disposable lab")
    tmp = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _digest(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _check(identifier: str, name: str, passed: bool, observed: str, expected: str, detail: str) -> dict:
    return dict(id=identifier, name=name, passed=bool(passed), observed=observed,
                expected=expected, detail=detail)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _healthy(checks: list[dict]) -> bool:
    return bool(checks) and all(c["passed"] for c in checks)


class DockerLab:
    """Sequential local operator workflow; persisted state is not a distributed lock."""

    def __init__(self, root: Path | None = None, slot: int = 120,
                 runner: CommandRunner | None = None):
        self.root = (root or (Path.cwd() / ".proofops-runtime")).resolve()
        if not 20 <= slot <= 219:
            raise ValueError("slot must be 20..219 (sandbox uses slot + 1)")
        self.slot = slot
        self.runner = runner or CommandRunner()
        self.lock = RLock()
        self.record_file = self.root / "controller.json"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def initial_config() -> dict[str, Any]:
        return {"dns_target": "edge", "proxy_target": "backend-a", "backend_a_running": True}

    def _state(self) -> dict:
        if not self.record_file.exists():
            raise LabConflict("Real Docker lab has not been started. Run `proofops-docker start` first.")
        if self.record_file.is_symlink():
            raise DockerLabError("Refusing symlinked state file")
        state = json.loads(self.record_file.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-f0-9]{10}", state.get("lab_id", "")):
            raise DockerLabError("Invalid lab ID in local state")
        return state

    def _save(self, state: dict) -> None:
        _atomic_text(self.record_file, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def _stack(self, state: dict, verification: bool = False) -> ComposeStack:
        part = "v" if verification else "a"
        return ComposeStack(self.root, f"proofops-{part}-{state['lab_id']}",
                            state["slot"] + (1 if verification else 0), self.runner)

    @staticmethod
    def _wait(stack: ComposeStack, predicate, *, duration: float = 12.0) -> list[dict]:
        deadline = monotonic() + duration
        last = []
        while monotonic() < deadline:
            last = stack.inspect()
            if predicate(last):
                return last
            sleep(0.75)
        return last

    def start(self) -> dict:
        with self.lock:
            if self.record_file.exists():
                raise LabConflict("Lab is already initialized. Use `status`, `reset`, or `stop`.")
            state = {"lab_id": secrets.token_hex(5), "slot": self.slot,
                     "revision": 1, "config": self.initial_config(), "active_incident": None,
                     "history": [], "created_at": _now()}
            stack = self._stack(state)
            stack.init_files(state["config"])
            try:
                stack.run("up", "-d", "--build", timeout=240)
                checks = self._wait(stack, _healthy)
                if not _healthy(checks):
                    raise DockerLabError("Docker stack started but actual DNS/HTTP probes did not pass: " +
                                         json.dumps(checks))
                self._save(state)
                return self.status()
            except Exception:
                stack.run("down", "--remove-orphans", strict=False, timeout=60)
                raise

    def status(self) -> dict:
        with self.lock:
            state = self._state()
            stack = self._stack(state)
            checks = stack.inspect()
            return {"lab_type": "real-docker", "live_infrastructure": True,
                    "project": stack.project, "revision": state["revision"],
                    "service_status": "healthy" if _healthy(checks) else "critical",
                    "checks": checks, "active_incident": state["active_incident"],
                    "history": state["history"], "fingerprint": stack.fingerprint(checks),
                    "scenario_options": SCENARIOS,
                    "warning": "Disposable Docker-only lab, not production infrastructure"}

    def _apply(self, stack: ComposeStack, action: str, config: dict) -> dict:
        if action not in ACTIONS:
            raise LabConflict("No safe allowlisted repair was available")
        updated = dict(config)
        if action == "restore_dns":
            stack.set_dns("edge")
            updated["dns_target"] = "edge"
        elif action == "restore_proxy":
            stack.set_proxy("backend-a")
            updated["proxy_target"] = "backend-a"
        elif action == "failover":
            standby = next((c for c in stack.inspect() if c["id"] == "standby"), None)
            if not standby or not standby["passed"]:
                raise LabConflict("Standby is unavailable; refusing failover")
            stack.set_proxy("backend-b")
            updated["proxy_target"] = "backend-b"
        return updated

    def _restore_base(self, stack: ComposeStack) -> list[dict]:
        stack.write_config(self.initial_config())
        stack.run("start", "backend-a", timeout=30)
        stack.reload_edge()
        return self._wait(stack, _healthy)

    def inject(self, scenario: str) -> dict:
        with self.lock:
            if scenario not in SCENARIOS:
                raise ValueError("Scenario must be one of: " + ", ".join(SCENARIOS))
            state = self._state()
            active = state["active_incident"]
            if active and active["status"] != "recovered":
                raise LabConflict("Resolve or reset the active incident before injecting another")
            stack = self._stack(state)
            before = self._restore_base(stack) if active else self._wait(stack, _healthy)
            if not _healthy(before):
                raise LabConflict("Cannot inject: real infrastructure baseline is not healthy")
            config = self.initial_config()
            try:
                if scenario == "dns-drift":
                    stack.set_dns("wrong")
                    config["dns_target"] = "wrong"
                elif scenario == "proxy-misroute":
                    stack.set_proxy("bogus")
                    config["proxy_target"] = "bogus"
                else:
                    stack.set_backend_a(False)
                    config["backend_a_running"] = False
                expected_failure = {"dns-drift": "dns-record",
                                    "proxy-misroute": "proxy-route",
                                    "backend-outage": "upstream-health"}[scenario]
                checks = self._wait(stack, lambda c: not _healthy(c) and
                                    not next(c2["passed"] for c2 in c if c2["id"] == "e2e") and
                                    not next(c2["passed"] for c2 in c if c2["id"] == expected_failure))
                if _healthy(checks) or next(c["passed"] for c in checks if c["id"] == "e2e"):
                    raise DockerLabError("Fault did not produce an observed end-to-end failure")
            except Exception:
                self._restore_base(stack)
                raise
            state["revision"] += 1
            state["config"] = config
            state["active_incident"] = {
                "id": secrets.token_hex(6), "scenario": scenario, "status": "open",
                "opened_at": _now(), "before": checks,
                "evidence_fingerprint": stack.fingerprint(checks),
                "action": None, "verification": None, "proof": None,
            }
            self._save(state)
            return self.status()

    @staticmethod
    def _guard_qualified_investigation(incident: dict) -> None:
        """Keep an approved hosted-AI decision intact until repair/reset.

        A new incident is the correct way to run another evaluation. Unqualified
        outcomes remain replaceable by the local baseline for safe recovery.
        """
        if (str(incident.get("diagnostic_source", "")).startswith(("openrouter-free:", "hosted-muse:"))
                and (incident.get("evidence_gate") or {}).get("allowed") is True
                and incident.get("action") in ACTIONS):
            if incident.get("status") == "verified":
                raise LabConflict("Qualified hosted-AI repair already verified; approve or reset")
            raise LabConflict("Qualified hosted-AI diagnosis is locked; verify it or reset the lab")

    def analyze(self) -> dict:
        with self.lock:
            state = self._state()
            incident = self._require_active(state)
            self._guard_qualified_investigation(incident)
            checks = self._stack(state).inspect()
            c = {item["id"]: item["passed"] for item in checks}
            # Evidence-only local baseline. Does not receive `scenario` labels or Meta output.
            if not c.get("dns-record") and c.get("proxy-route"):
                action = "restore_dns"
            elif c.get("dns-record") and not c.get("proxy-route"):
                action = "restore_proxy"
            elif c.get("dns-record") and c.get("proxy-route") and \
                    not c.get("upstream-health") and c.get("standby"):
                action = "failover"
            else:
                action = "none"
            incident["action"] = action
            incident["status"] = "diagnosed"
            incident["verification"] = None
            incident["diagnostic_checks"] = checks
            incident["diagnostic_source"] = "real-probe-rules (not Meta)"
            incident["investigation"] = None
            incident["raw_action"] = None
            incident["evidence_gate"] = None
            self._save(state)
            return self.status()

    def investigate(self, agent=None, *, label: str | None = None) -> dict:
        """Read-only tool investigation on the active stack, without scenario or state config hints.

        The default agent is a deterministic benchmark baseline, NOT Meta AI.
        Neither the agent nor the tools may invoke the repair executor. As with
        analyze(), a proposal is non-binding until verify() succeeds in a replica.
        """
        from .investigation import RealReadOnlyTools, ReferenceInvestigator, investigate_readonly
        from .evidence_gate import assess_proposal
        with self.lock:
            state = self._state()
            incident = self._require_active(state)
            self._guard_qualified_investigation(incident)
            stack = self._stack(state)
            before = stack.inspect()
            if _healthy(before):
                raise LabConflict("Active customer service is healthy; refusing unnecessary repair")
            fingerprint = stack.fingerprint(before)
            source_label = label or ("read-only-reference-baseline (NOT AI)" if agent is None
                                     else "external-read-only-investigator (NOT VERIFIED AI)")
            tools = RealReadOnlyTools(stack)
            result = investigate_readonly(tools,
                                         agent if agent is not None else ReferenceInvestigator(),
                                         label=source_label)
            after = stack.inspect()
            if stack.fingerprint(after) != fingerprint or state["revision"] != self._state()["revision"]:
                raise LabConflict("Live evidence changed during investigation; retry from a stable state")
            proposal = result["proposal"]
            # A model's valid JSON is still untrusted. A repair is promoted into
            # the controller only after the INDEPENDENT evidence gate accepts
            # actual read-only Docker probes and the model's original citations.
            # Never replace the model's raw action or silently fill citations.
            verdict = assess_proposal(proposal, tools.observations)
            incident["raw_action"] = proposal["action"]
            incident["evidence_gate"] = verdict.public()
            incident["action"] = (proposal["action"] if verdict.allowed and
                                  proposal["action"] in ACTIONS else "none")
            incident["status"] = "diagnosed"
            incident["verification"] = None
            incident["diagnostic_checks"] = after
            incident["diagnostic_source"] = proposal["source"]
            incident["investigation"] = result
            self._save(state)
            return self.status()

    @staticmethod
    def _require_active(state: dict) -> dict:
        incident = state["active_incident"]
        if not incident or incident["status"] == "recovered":
            raise LabConflict("No unrecovered incident is active")
        return incident

    def verify(self) -> dict:
        with self.lock:
            state = self._state()
            incident = self._require_active(state)
            action = incident.get("action")
            if action not in ACTIONS:
                raise LabConflict("Run analyze first; an unsafe or unknown action cannot be verified")
            if incident.get("investigation") is not None:
                gate = incident.get("evidence_gate")
                raw = incident["investigation"].get("proposal", {}).get("action")
                if not isinstance(gate, dict) or gate.get("allowed") is not True or raw != action:
                    raise LabConflict("Independent evidence gate has not accepted this investigation")
            active = self._stack(state)
            live_before = active.inspect()
            if _healthy(live_before):
                raise LabConflict("Active stack unexpectedly healthy. Refusing to use stale diagnosis")
            if state["config"] != self._reconciled_config(state):
                raise LabConflict("On-disk configuration changed outside the controller")
            verified_fingerprint = active.fingerprint(live_before)
            sandbox = self._stack(state, verification=True)
            sandbox.init_files(state["config"])
            sandbox_attempted = False
            cleanup_error = None
            result: dict[str, Any] | None = None
            try:
                # Clone fault and physical backend availability, NOT just inferred in-memory state.
                sandbox_attempted = True
                sandbox.run("up", "-d", "--build", timeout=240)
                if not state["config"]["backend_a_running"]:
                    sandbox.set_backend_a(False)
                active_failures = {c["id"] for c in live_before if not c["passed"]}
                sandbox_before = self._wait(sandbox,
                                            lambda c: {x["id"] for x in c if not x["passed"]}
                                            == active_failures and not _healthy(c))
                sandbox_failures = {c["id"] for c in sandbox_before if not c["passed"]}
                if _healthy(sandbox_before) or active_failures != sandbox_failures:
                    raise LabConflict("Verification clone failed to reproduce the original fault signature")
                updated = self._apply(sandbox, action, state["config"])
                sandbox_after = self._wait(sandbox, _healthy)
                if not _healthy(sandbox_after):
                    raise LabConflict("The proposed action did not restore all actual sandbox probes")
                result = {"action": action, "success": True,
                          "sandbox_before": sandbox_before, "sandbox_after": sandbox_after,
                          "sandbox_configuration": updated, "source_fingerprint": verified_fingerprint,
                          "source_revision": state["revision"], "verified_at": _now(),
                          "note": "Second real Docker Compose stack, not an in-memory clone"}
                result["proof_digest"] = _digest(result)
            finally:
                # Always remove only the sandbox project, including on validation failure.
                if sandbox_attempted:
                    down = sandbox.run("down", "--remove-orphans", timeout=80, strict=False)
                    if down.code:
                        cleanup_error = down.stderr[-400:]
                if cleanup_error:
                    raise DockerLabError("Sandbox verification cleanup failed: " + cleanup_error)
                if sandbox.stack_dir.exists():
                    shutil.rmtree(sandbox.stack_dir)
            if result is None:
                raise DockerLabError("Unexpected incomplete sandbox verification")
            incident["verification"] = result
            incident["status"] = "verified"
            self._save(state)
            return self.status()

    def _reconciled_config(self, state: dict) -> dict:
        stack = self._stack(state)
        expected = dict(state["config"])
        dns = _read_file(stack.stack_dir / "dns" / "hosts")
        nginx = _read_file(stack.stack_dir / "nginx" / "default.conf")
        dns_addr = stack.edge_ip if expected["dns_target"] == "edge" else stack.wrong_ip
        proxy_addr = {"backend-a": stack.backend_a_ip, "backend-b": stack.backend_b_ip,
                      "bogus": stack.wrong_ip}[expected["proxy_target"]]
        if dns.strip() != f"{dns_addr} {APP_HOST}" or \
                f"proxy_pass http://{proxy_addr}:8080;" not in nginx:
            return {}
        return expected

    def repair(self, *, approved: bool, expected_revision: int, confirmation: str) -> dict:
        with self.lock:
            state = self._state()
            incident = self._require_active(state)
            verification = incident.get("verification")
            if not approved or confirmation != CONFIRM_PHRASE:
                raise LabConflict("Explicit approval and exact confirmation phrase are required")
            if not verification or incident["status"] != "verified":
                raise LabConflict("Successful independent sandbox verification required")
            if expected_revision != state["revision"] or verification["source_revision"] != state["revision"]:
                raise LabConflict("Stale revision — verify again")
            stack = self._stack(state)
            latest = stack.inspect()
            if stack.fingerprint(latest) != verification["source_fingerprint"] or \
                    not self._reconciled_config(state):
                raise LabConflict("Observed state or config has drifted — verify again")
            original = dict(state["config"])
            try:
                updated = self._apply(stack, verification["action"], original)
                after = self._wait(stack, _healthy)
                if not _healthy(after):
                    raise DockerLabError("Post-apply real health checks failed")
            except Exception as exc:
                # Rollback only the three configurations / processes scoped to our Compose stack.
                try:
                    stack.write_config(original)
                    stack.set_backend_a(original["backend_a_running"])
                    stack.reload_edge()
                    self._wait(stack, lambda c: not _healthy(c), duration=8)
                except Exception as rollback_exc:
                    incident["status"] = "rollback-failed"
                    incident["rollback_error"] = type(rollback_exc).__name__
                    self._save(state)
                    raise DockerLabError("Repair failed AND rollback failed; operator must inspect the lab") from exc
                incident["status"] = "diagnosed"
                incident["verification"] = None
                self._save(state)
                raise DockerLabError("Real repair failed; original lab configuration restored") from exc
            state["revision"] += 1
            state["config"] = updated
            incident["status"] = "recovered"
            incident["recovered_at"] = _now()
            incident["proof"] = {
                "result": "observed-recovery-in-disposable-docker-lab",
                "verification_digest": verification["proof_digest"],
                "before": latest, "after": after,
                "before_fingerprint": verification["source_fingerprint"],
                "after_fingerprint": stack.fingerprint(after),
                "action": verification["action"], "revision": state["revision"],
                "diagnostic_source": incident.get("diagnostic_source"),
                "raw_action": incident.get("raw_action"),
                "evidence_gate": incident.get("evidence_gate"),
                "investigation_digest": (_digest(incident["investigation"])
                                         if incident.get("investigation") else None),
            }
            incident["proof"]["proof_digest"] = _digest(incident["proof"])
            state["history"].append({"id": incident["id"], "scenario": incident["scenario"],
                                     "recovered_at": incident["recovered_at"],
                                     "proof_digest": incident["proof"]["proof_digest"],
                                     "diagnostic_source": incident.get("diagnostic_source"),
                                     "raw_action": incident.get("raw_action")})
            self._save(state)
            return self.status()

    def reset(self) -> dict:
        with self.lock:
            state = self._state()
            stack = self._stack(state)
            checks = self._restore_base(stack)
            if not _healthy(checks):
                raise DockerLabError("Real stack did not become healthy after reset")
            state["revision"] += 1
            state["config"] = self.initial_config()
            state["active_incident"] = None
            self._save(state)
            return self.status()

    def stop(self) -> dict:
        with self.lock:
            state = self._state()
            for stack in [self._stack(state, verification=True), self._stack(state)]:
                stack.run("down", "--remove-orphans", timeout=90)
            self.record_file.unlink()
            return {"status": "stopped", "project": self._stack(state).project,
                    "note": "Only ProofOps Compose resources were stopped; evidence files retained"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ProofOps disposable REAL Docker Compose lab; hosted AI is explicitly opt-in")
    parser.add_argument("command", choices=("start", "status", "inject", "analyze", "verify",
                                             "repair", "reset", "stop", "investigate"))
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--investigator", choices=("reference", "adaptive", "wire-emulator", "ollama-local", "openrouter-free", "hosted-muse"),
                        default="reference", help="Read-only investigation; hosted Muse is separate explicit opt-in")
    parser.add_argument("--local-model", choices=("llama3.1:8b", "llama3.2:3b"),
                        default="llama3.1:8b", help="Used only by explicit ollama-local investigator")
    parser.add_argument("--muse-provider", choices=("official-meta", "baseten"),
                        help="Explicit hosted Muse provider (never inferred from MODEL_API_KEY)")
    parser.add_argument("--slot", type=int, default=120,
                        help="Private subnet: 10.223.SLOT.0/24; sandbox uses SLOT+1")
    parser.add_argument("--confirm", default="", help=f'For repair, enter "{CONFIRM_PHRASE}"')
    parser.add_argument("--confirm-cloud", default="",
                        help="Explicit opt-in phrase for selected hosted investigator; no implicit cloud use")
    parser.add_argument("--revision", type=int, help="State revision obtained from status")
    parser.add_argument("--root", type=Path, default=Path.cwd() / ".proofops-runtime")
    args = parser.parse_args(argv)
    if args.command == "investigate" and args.investigator == "openrouter-free":
        if args.confirm_cloud != CLOUD_CONSENT_PHRASE:
            parser.error(f'Hosted model requires --confirm-cloud "{CLOUD_CONSENT_PHRASE}"; '
                         'the free provider receives only fixed, bounded generated Docker lab probes. '
                         'No private workloads, logs, or repair commands are uploaded.')
        if not os.environ.get("OPENROUTER_API_KEY"):
            parser.error("Set OPENROUTER_API_KEY privately before the explicit cloud investigation")
    if args.command == "investigate" and args.investigator == "hosted-muse":
        from .hosted_muse import SPECS
        if args.muse_provider is None:
            parser.error("Hosted Muse requires --muse-provider official-meta or baseten")
        if args.confirm_cloud != HOSTED_MUSE_CONSENT_PHRASE:
            parser.error("Hosted Muse requires explicit --confirm-cloud consent for bounded "
                         "disposable Docker observations; hosted calls may be billed")
        secret_name = SPECS[args.muse_provider]["key_env"]
        if not os.environ.get(secret_name):
            parser.error(f"Set {secret_name} privately before hosted Muse inference")
    lab = DockerLab(root=args.root, slot=args.slot)
    try:
        if args.command == "start":
            result = lab.start()
        elif args.command == "status":
            result = lab.status()
        elif args.command == "inject":
            if not args.scenario:
                parser.error("inject requires --scenario")
            result = lab.inject(args.scenario)
        elif args.command == "analyze":
            result = lab.analyze()
        elif args.command == "investigate":
            if args.investigator == "adaptive":
                from .blind_eval import AdaptiveRuleInvestigator
                result = lab.investigate(agent=AdaptiveRuleInvestigator(),
                                         label="adaptive-rule-baseline (NOT AI)")
            elif args.investigator == "wire-emulator":
                from .model_protocol import DeterministicWireProvider, PROVIDER_LABEL, WireInvestigator
                result = lab.investigate(agent=WireInvestigator(DeterministicWireProvider()),
                                         label=PROVIDER_LABEL)
            elif args.investigator == "ollama-local":
                from .model_protocol import OllamaLocalProvider, WireInvestigator
                result = lab.investigate(
                    agent=WireInvestigator(OllamaLocalProvider(args.local_model)),
                    label=f"local-meta-openweights:{args.local_model} (NOT MUSE)")
            elif args.investigator == "hosted-muse":
                from .hosted_muse import HostedMuseProvider
                from .model_protocol import WireInvestigator
                provider = HostedMuseProvider(args.muse_provider)
                print("Explicitly authorized hosted Muse inference using only "
                      "bounded disposable Docker observations; no private logs "
                      "or automatic repair.", file=sys.stderr, flush=True)
                result = lab.investigate(agent=WireInvestigator(provider),
                                         label=provider.source_label)
                incident = result["active_incident"]
                result["hosted_model_usage"] = {
                    "provider": provider.provider,
                    "requested_model": provider.model,
                    "returned_models": provider.returned_models,
                    "requests": provider.calls,
                    "input_tokens": provider.prompt_tokens,
                    "output_tokens": provider.completion_tokens,
                    "reasoning_tokens": provider.reasoning_tokens,
                    "raw_action": incident["raw_action"],
                    "promoted_action": incident["action"],
                    "evidence_gate": incident["evidence_gate"],
                }
            elif args.investigator == "openrouter-free":
                from .model_protocol import WireInvestigator
                from .openrouter_free import FreeModelProvider
                print("Explicitly authorized: sending only bounded disposable lab topology, "
                      "DNS, Nginx and HTTP health observations to OpenRouter; "
                      "no private logs, repairs or paid-model fallback.", flush=True)
                provider = FreeModelProvider(progress=lambda event: print(event, flush=True))
                result = lab.investigate(agent=WireInvestigator(provider),
                                         label=f"openrouter-free:{provider.model} (NOT META MUSE)")
                incident = result["active_incident"]
                result["hosted_model_usage"] = {
                    "model": provider.model,
                    "requests": provider.calls,
                    "input_tokens": provider.prompt_tokens,
                    "output_tokens": provider.completion_tokens,
                    "reasoning_tokens": provider.reasoning_tokens,
                    "exact_choice_recoveries": provider.compact_choice_recoveries,
                    "raw_action": incident["raw_action"],
                    "promoted_action": incident["action"],
                    "evidence_gate": incident["evidence_gate"],
                }
            else:
                result = lab.investigate()
        elif args.command == "verify":
            result = lab.verify()
        elif args.command == "repair":
            if args.revision is None:
                parser.error("repair requires --revision from the verify/status output")
            result = lab.repair(approved=True, expected_revision=args.revision,
                                confirmation=args.confirm)
        elif args.command == "reset":
            result = lab.reset()
        else:
            result = lab.stop()
        print(json.dumps(result, indent=2))
        return 0
    except (DockerLabError, ValueError) as exc:
        print(f"ProofOps Docker lab: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
