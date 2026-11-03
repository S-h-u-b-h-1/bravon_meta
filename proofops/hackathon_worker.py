"""Bounded Docker verification for committed first-party hackathon fixtures."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time

from bravon_provenance import SignedEvidence, sign_evidence
from bravon_verification import Observation


IMAGE = "python:3.12-alpine@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d"
MAX_REPLACEMENT_BYTES = 20_000
MAX_OUTPUT_BYTES = 8_000
TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class FixtureCase:
    id: str
    domain: str
    summary: str
    root: Path
    target_file: str
    public_test: str
    hidden_test: str


@dataclass(frozen=True)
class RepairProposal:
    case_id: str
    target_file: str
    replacement: str
    rationale: str
    evidence_ids: tuple[str, ...]
    confidence: float

    def validate(self, case: FixtureCase) -> None:
        if self.case_id != case.id or self.target_file != case.target_file:
            raise ValueError("Repair must target the case's allowlisted file")
        if Path(self.target_file).is_absolute() or Path(self.target_file).parts != (self.target_file,):
            raise ValueError("Repair path must be a single relative filename")
        if not isinstance(self.replacement, str) or not self.replacement.strip():
            raise ValueError("Replacement source is required")
        if len(self.replacement.encode("utf-8")) > MAX_REPLACEMENT_BYTES:
            raise ValueError("Replacement exceeds the patch-size limit")
        if (not isinstance(self.rationale, str) or not self.rationale.strip()
                or not isinstance(self.evidence_ids, tuple) or not self.evidence_ids
                or any(not isinstance(value, str) or not value for value in self.evidence_ids)
                or type(self.confidence) not in (int, float)
                or not 0 <= self.confidence <= 1):
            raise ValueError("Rationale, evidence identifiers and bounded confidence are required")


@dataclass(frozen=True)
class TestRun:
    test_file: str
    run_id: str
    status: str
    exit_code: int | None
    duration_ms: int
    output: str


@dataclass(frozen=True)
class VerificationReport:
    schema: str
    case_id: str
    domain: str
    verdict: str
    before_public: TestRun
    after_public: TestRun
    after_hidden: TestRun
    image_digest: str
    network: str
    proposal_sha256: str
    duration_ms: int


def report_digest(report: VerificationReport) -> str:
    payload = json.dumps(
        asdict(report), sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def sign_verification_report(
    report: VerificationReport, *, runner_id: str, key_id: str, secret: bytes,
) -> SignedEvidence:
    case_id = f"{report.case_id}:{report.after_public.run_id}:{report.after_hidden.run_id}"
    observation = Observation(
        evidence_id="verification-report-digest",
        key="verification_report_sha256",
        value=report_digest(report),
        source=runner_id,
        environment_fingerprint=report.image_digest,
    )
    return sign_evidence(
        runner_id=runner_id, key_id=key_id, case_id=case_id,
        nonce=secrets.token_hex(16), observations=(observation,), secret=secret,
    )


def load_cases(root: Path) -> dict[str, FixtureCase]:
    cases: dict[str, FixtureCase] = {}
    for path in sorted(root.glob("*/case.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case = FixtureCase(root=path.parent, **data)
        if (case.id in cases or Path(case.target_file).parts != (case.target_file,)
                or Path(case.public_test).parts != (case.public_test,)
                or Path(case.hidden_test).parts != (case.hidden_test,)):
            raise ValueError("Fixture identifiers and files must be unique bounded filenames")
        for name in (case.target_file, case.public_test, case.hidden_test):
            if not (case.root / name).is_file():
                raise ValueError(f"Fixture file missing: {name}")
        cases[case.id] = case
    return cases


def _image_digest() -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI unavailable")
    result = subprocess.run(
        [docker, "image", "inspect", IMAGE, "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    digest = result.stdout.strip()
    if result.returncode or not digest.startswith("sha256:") or len(digest) != 71:
        raise RuntimeError(f"Pinned worker image unavailable: run 'docker pull {IMAGE}'")
    return digest


def _classify(returncode: int, output: str) -> str:
    if returncode == 0:
        return "PASS"
    if "AssertionError" in output or "FAILED (failures=" in output:
        return "ASSERT_FAIL"
    return "ERROR"


def _run_test(workspace: Path, test_file: str, image_digest: str) -> TestRun:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI unavailable")
    run_id = secrets.token_hex(8)
    name = f"bravon-worker-{run_id}"
    command = [
        docker, "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "128m",
        "--cpus", "0.5", "--pids-limit", "64", "--user", "65534:65534",
        # Docker mounts this private noexec tmpfs; it is not a host temporary file.
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",  # nosec B108
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{workspace.resolve()}:/workspace:ro", "-w", "/workspace",
        image_digest, "python", "-m", "unittest", "-q", test_file,
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False,
        )
        output = (result.stdout + result.stderr)[-MAX_OUTPUT_BYTES:]
        status, exit_code = _classify(result.returncode, output), result.returncode
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or ""))[-MAX_OUTPUT_BYTES:]
        status, exit_code = "TIMEOUT", None
    finally:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=5, check=False)
    return TestRun(test_file, run_id, status, exit_code,
                   int((time.monotonic() - started) * 1000), output)


def reproduce_failure(case: FixtureCase) -> tuple[TestRun, str]:
    image_digest = _image_digest()
    with tempfile.TemporaryDirectory(prefix="bravon-reproduce-") as directory:
        workspace = Path(directory) / "before"
        shutil.copytree(case.root, workspace)
        return _run_test(workspace, case.public_test, image_digest), image_digest


def verify_candidate(case: FixtureCase, proposal: RepairProposal) -> VerificationReport:
    proposal.validate(case)
    image_digest = _image_digest()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="bravon-worker-") as directory:
        before_root = Path(directory) / "before"
        after_root = Path(directory) / "after"
        shutil.copytree(case.root, before_root)
        shutil.copytree(case.root, after_root)
        before = _run_test(before_root, case.public_test, image_digest)
        if before.status != "ASSERT_FAIL":
            verdict = "INCONCLUSIVE_ORIGINAL_NOT_REPRODUCED"
            after_public = TestRun(case.public_test, "not-run", "NOT_RUN", None, 0, "")
            after_hidden = TestRun(case.hidden_test, "not-run", "NOT_RUN", None, 0, "")
        else:
            (after_root / case.target_file).write_text(proposal.replacement, encoding="utf-8")
            after_public = _run_test(after_root, case.public_test, image_digest)
            after_hidden = _run_test(after_root, case.hidden_test, image_digest)
            if after_public.status != "PASS":
                verdict = "REJECTED_REGRESSION_STILL_FAILS"
            elif after_hidden.status != "PASS":
                verdict = "REJECTED_FALSE_GREEN"
            else:
                verdict = "VERIFIED"
    return VerificationReport(
        schema="bravon.hackathon-verification.v1", case_id=case.id, domain=case.domain,
        verdict=verdict, before_public=before, after_public=after_public,
        after_hidden=after_hidden, image_digest=image_digest, network="none",
        proposal_sha256="sha256:" + sha256(proposal.replacement.encode()).hexdigest(),
        duration_ms=int((time.monotonic() - started) * 1000),
    )
