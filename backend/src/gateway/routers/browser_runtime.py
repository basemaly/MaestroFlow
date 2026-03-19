from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.gateway.contracts import build_error_envelope, build_health_envelope
from src.integrations.browser_runtime import create_browser_job, get_browser_runtime_config, get_job, list_jobs

router = APIRouter(prefix="/api/browser-runtime", tags=["browser-runtime"])


class BrowserJobRequestModel(BaseModel):
    action: str = Field(min_length=1)
    url: str | None = None
    runtime: str = "playwright"
    target: str | None = None
    input: dict = Field(default_factory=dict)
    benchmark_id: str | None = None
    script: str | None = None


@router.get("/config")
async def browser_runtime_config() -> dict:
    config = get_browser_runtime_config()
    return {
        "base_url": config.lightpanda_base_url or "",
        "configured": config.enabled,
        "enabled": config.enabled,
        "available": True,
        "default_runtime": config.default_runtime,
        "supported_runtimes": ["auto", "playwright", "lightpanda"],
        "lightpanda_available": config.lightpanda_available,
        "warning": None if config.enabled else "Browser runtime is disabled.",
        "health": build_health_envelope(
            configured=config.enabled,
            available=True,
            healthy=True,
            summary="Browser runtime bridge ready.",
            metrics={"lightpanda_available": int(config.lightpanda_available)},
        ),
        "error": None,
    }


@router.post("/jobs")
async def browser_runtime_jobs(req: BrowserJobRequestModel) -> dict:
    try:
        payload = req.model_dump()
        if not payload.get("url") and payload.get("target"):
            payload["url"] = payload["target"]
        if payload.get("script") and not payload.get("input"):
            payload["input"] = {"script": payload["script"]}
        job = await create_browser_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "available": True,
        "warning": job.get("result", {}).get("warning"),
        "error": None,
        "job": {
            "job_id": job["job_id"],
            "runtime": job["runtime_used"],
            "action": job["action"],
            "status": job["status"],
            "url": job["request"].get("url"),
            "target": job["request"].get("target"),
            "summary": f"{job['action']} finished with status {job['status']}.",
            "result": job["result"],
            "error": None,
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        },
    }


@router.get("/jobs")
async def browser_runtime_list_jobs() -> dict:
    jobs = list_jobs()
    return {
        "available": True,
        "warning": None,
        "error": None,
        "jobs": [
            {
                "job_id": job["job_id"],
                "runtime": job["runtime_used"],
                "action": job["action"],
                "status": job["status"],
                "url": job["request"].get("url"),
                "target": job["request"].get("target"),
                "summary": f"{job['action']} finished with status {job['status']}.",
                "result": job["result"],
                "error": None,
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
            }
            for job in jobs
        ],
    }


@router.get("/jobs/{job_id}")
async def browser_runtime_get_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown browser job '{job_id}'.")
    return {
        "available": True,
        "warning": job["result"].get("warning") if isinstance(job.get("result"), dict) else None,
        "job": {
            "job_id": job["job_id"],
            "runtime": job["runtime_used"],
            "action": job["action"],
            "status": job["status"],
            "url": job["request"].get("url"),
            "target": job["request"].get("target"),
            "summary": f"{job['action']} finished with status {job['status']}.",
            "result": job["result"],
            "error": None,
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        },
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=job["status"] == "succeeded",
            summary=f"Browser job is {job['status']}.",
        ),
        "error": None if job["status"] == "succeeded" else build_error_envelope(error_code="browser_job_degraded", message="Browser job completed in degraded mode.", retryable=False),
    }
