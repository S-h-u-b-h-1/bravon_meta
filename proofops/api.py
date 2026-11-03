"""Small HTTP API and local UI. Never expose this unauthenticated demo on a public network."""

import os
import json
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core import IncidentLab, ConflictError, NotFoundError
from .real_lab import DockerLab, DockerLabError, LabConflict, CONFIRM_PHRASE

# Known fixed report paths. Tests override only this named constant, not the
# production user's local report files. Never accept arbitrary paths over HTTP.
_MODEL_TRIAL_ROOT = Path(__file__).resolve().parents[1]
MODEL_TRIALS_REPORT = _MODEL_TRIAL_ROOT / "reports" / "model-trials-v081.html"
MODEL_TRIALS_PREVIEW = _MODEL_TRIAL_ROOT / "docs" / "model-trials-v081-DEMO-MOCK.html"
HACKATHON_EVIDENCE_ROOT = _MODEL_TRIAL_ROOT / "docs" / "evidence"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "testserver")
_RUN_ID = re.compile(r"^[a-z0-9-]{1,120}$")


class DiagnoseRequest(BaseModel):
    use_meta: bool = False


class ExecuteRequest(BaseModel):
    approved: bool
    expected_revision: int


class DockerStartRequest(BaseModel):
    confirmation: str


class DockerRepairRequest(BaseModel):
    approved: bool
    expected_revision: int
    confirmation: str


def create_app(lab: IncidentLab | None = None, docker_lab: DockerLab | None = None) -> FastAPI:
    instance = lab or IncidentLab()
    app = FastAPI(title="Bravon local lab", version="0.9.0")
    docker_enabled = os.environ.get("PROOFOPS_ENABLE_DOCKER_UI") == "1" or docker_lab is not None
    active_docker_lab = docker_lab if docker_lab is not None else (DockerLab(
        root=Path(__file__).resolve().parents[1] / ".proofops-runtime"
    ) if docker_enabled else None)
    app.state.lab = instance
    web_root = Path(__file__).resolve().parents[1] / "web"
    if web_root.is_dir():
        app.mount("/assets", StaticFiles(directory=web_root), name="assets")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        return response

    def current_lab() -> IncidentLab:
        return app.state.lab

    def local_only(request: Request) -> bool:
        return request.url.hostname in LOCAL_HOSTS and not os.environ.get("VERCEL")

    def simulation_local_write(request: Request) -> None:
        if not local_only(request):
            raise HTTPException(403, "Public Bravon is read-only; run investigations on the local operator app")

    def handle(exc: Exception):
        if isinstance(exc, NotFoundError):
            raise HTTPException(404, str(exc)) from exc
        if isinstance(exc, (ConflictError, ValueError)):
            raise HTTPException(409, str(exc)) from exc
        raise exc

    @app.get("/")
    def home():
        return FileResponse(web_root / "hackathon.html")

    @app.get("/simulation")
    def simulation_console():
        return FileResponse(web_root / "index.html")

    @app.get("/muse")
    def muse_evidence_console():
        """Public, read-only official Muse evidence explorer; no inference endpoints."""
        return FileResponse(web_root / "muse-evidence.html")

    @app.get("/docker")
    def docker_console():
        return FileResponse(web_root / "docker.html")

    @app.get("/model-trials")
    def model_trials_console():
        """Serve only the known synthetic trial report, never arbitrary files."""
        report = MODEL_TRIALS_REPORT if MODEL_TRIALS_REPORT.is_file() else MODEL_TRIALS_PREVIEW
        if not report.is_file():
            raise HTTPException(404, "No model trial scorecard generated")
        return FileResponse(report, media_type="text/html",
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    def docker_local_write(request: Request) -> DockerLab:
        if active_docker_lab is None:
            raise HTTPException(403, "Real Docker controls disabled. Set PROOFOPS_ENABLE_DOCKER_UI=1 explicitly.")
        # Defense against cross-origin drive-by requests to unauthenticated localhost.
        if not local_only(request):
            raise HTTPException(403, "Docker controls must run on loopback")
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get("host"):
                raise HTTPException(403, "Cross-origin Docker commands forbidden")
        if request.headers.get("x-proofops-local-intent") != "proofops-local-console":
            raise HTTPException(403, "Missing explicit local-console intent header")
        return active_docker_lab

    def docker_call(callback):
        try:
            return callback()
        except LabConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except DockerLabError as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/docker/status")
    def docker_status():
        if active_docker_lab is None:
            return {"enabled": False, "initialized": False,
                    "message": "Docker UI disabled; start with PROOFOPS_ENABLE_DOCKER_UI=1"}
        if not active_docker_lab.record_file.exists():
            return {"enabled": True, "initialized": False,
                    "message": "Ready to start disposable Docker containers"}
        return {"enabled": True, "initialized": True, **docker_call(active_docker_lab.status)}

    @app.post("/api/docker/start")
    def docker_start(payload: DockerStartRequest, request: Request):
        docker = docker_local_write(request)
        if payload.confirmation != "START LOCAL DOCKER LAB":
            raise HTTPException(409, "Explicit start confirmation required")
        return docker_call(docker.start)

    @app.post("/api/docker/inject/{scenario}")
    def docker_inject(scenario: str, request: Request):
        docker = docker_local_write(request)
        return docker_call(lambda: docker.inject(scenario))

    @app.post("/api/docker/analyze")
    def docker_analyze(request: Request):
        docker = docker_local_write(request)
        return docker_call(docker.analyze)

    @app.post("/api/docker/investigate")
    def docker_investigate(request: Request):
        docker = docker_local_write(request)
        return docker_call(docker.investigate)

    @app.post("/api/docker/verify")
    def docker_verify(request: Request):
        docker = docker_local_write(request)
        return docker_call(docker.verify)

    @app.post("/api/docker/repair")
    def docker_repair(payload: DockerRepairRequest, request: Request):
        docker = docker_local_write(request)
        return docker_call(lambda: docker.repair(approved=payload.approved,
                                                expected_revision=payload.expected_revision,
                                                confirmation=payload.confirmation))

    @app.post("/api/docker/reset")
    def docker_reset(payload: DockerStartRequest, request: Request):
        docker = docker_local_write(request)
        if payload.confirmation != "RESET LOCAL DOCKER LAB":
            raise HTTPException(409, "Explicit reset confirmation required")
        return docker_call(docker.reset)

    @app.post("/api/docker/stop")
    def docker_stop(payload: DockerStartRequest, request: Request):
        docker = docker_local_write(request)
        if payload.confirmation != "STOP LOCAL DOCKER LAB":
            raise HTTPException(409, "Explicit stop confirmation required")
        return docker_call(docker.stop)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "product": "Bravon", "mode": "evidence-dashboard"}

    def hackathon_runs() -> dict[str, dict]:
        runs = {}
        for path in sorted(HACKATHON_EVIDENCE_ROOT.glob("local-meta-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if payload.get("schema") == "bravon.meta-investigation.v1":
                runs[path.stem] = payload
        return runs

    @app.get("/api/hackathon/runs")
    def list_hackathon_runs():
        summaries = []
        for run_id, payload in hackathon_runs().items():
            investigation = payload["investigation"]
            verification = payload.get("verification")
            summaries.append({
                "id": run_id,
                "generated_at": payload["generated_at"],
                "case_id": investigation["case_id"],
                "model": investigation["model"],
                "source": investigation["source"],
                "inference": payload["inference"],
                "decision": "propose" if investigation.get("proposal") else "abstain",
                "verdict": verification["verdict"] if verification else "ABSTAINED",
                "requests": investigation["requests"],
                "input_tokens": investigation["input_tokens"],
                "output_tokens": investigation["output_tokens"],
                "cost_usd": investigation["cost_usd"],
            })
        summaries.sort(key=lambda item: item["generated_at"], reverse=True)
        return {"runs": summaries, "execution": "disabled-on-public-web"}

    @app.get("/api/hackathon/runs/{run_id}")
    def get_hackathon_run(run_id: str):
        if not _RUN_ID.fullmatch(run_id):
            raise HTTPException(404, "Evidence run not found")
        payload = hackathon_runs().get(run_id)
        if payload is None:
            raise HTTPException(404, "Evidence run not found")
        return payload

    @app.get("/api/config")
    def config(request: Request):
        meta_configured = bool(os.environ.get("MODEL_API_KEY")) and local_only(request)
        return {
            "provider": "Meta available (opt-in)" if meta_configured else "Evidence engine only",
            "meta_configured": meta_configured,
            "meta_model": os.environ.get("META_MODEL", "muse-spark-1.3"),
            "runtime": "LOCAL SIMULATION — not connected to real servers",
        }

    @app.get("/api/state")
    def state(service: Annotated[IncidentLab, Depends(current_lab)]):
        return service.snapshot()

    @app.post("/api/scenarios/{scenario}/inject")
    def inject(scenario: str, request: Request,
               service: Annotated[IncidentLab, Depends(current_lab)]):
        simulation_local_write(request)
        try:
            service.inject(scenario)
            return service.snapshot()
        except Exception as exc:
            handle(exc)

    @app.post("/api/incidents/{incident_id}/diagnose")
    def diagnose(incident_id: str, payload: DiagnoseRequest, request: Request,
                 service: Annotated[IncidentLab, Depends(current_lab)]):
        simulation_local_write(request)
        try:
            service.analyze(incident_id, payload.use_meta)
            return service.snapshot()
        except Exception as exc:
            handle(exc)

    @app.post("/api/incidents/{incident_id}/verify")
    def verify(incident_id: str, request: Request,
               service: Annotated[IncidentLab, Depends(current_lab)]):
        simulation_local_write(request)
        try:
            service.verify(incident_id)
            return service.snapshot()
        except Exception as exc:
            handle(exc)

    @app.post("/api/incidents/{incident_id}/execute")
    def execute(incident_id: str, payload: ExecuteRequest, request: Request,
                service: Annotated[IncidentLab, Depends(current_lab)]):
        simulation_local_write(request)
        try:
            service.execute(incident_id, payload.approved, payload.expected_revision)
            return service.snapshot()
        except Exception as exc:
            handle(exc)

    @app.post("/api/reset")
    def reset(request: Request, service: Annotated[IncidentLab, Depends(current_lab)]):
        simulation_local_write(request)
        return service.reset()

    return app


app = create_app()
