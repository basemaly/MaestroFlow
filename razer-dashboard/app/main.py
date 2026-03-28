import asyncio
import json
import os
import subprocess
import yaml
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Unified Dashboard API")

# Allow all origins (dashboard is internal only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CONFIG =====
CONFIG_DIR = Path(__file__).parent.parent / "config"
SERVICES_FILE = CONFIG_DIR / "services.yaml"
DEVICES_FILE = CONFIG_DIR / "allowed_devices.yaml"


# ===== DATA MODELS =====
class Service:
    def __init__(self, **data):
        self.__dict__.update(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Service":
        return cls(**data)

    def model_dump(self) -> dict:
        return self.__dict__


class ServiceControl:
    def __init__(self, action: str):
        self.action = action.lower()


class Device:
    def __init__(self, **data):
        self.__dict__.update(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Device":
        return cls(**data)


class DeviceOut:
    def __init__(self, **data):
        self.__dict__.update(data)


# ===== UTILITIES =====
def load_yaml(file_path: Path) -> dict:
    if not file_path.exists():
        return {}
    with open(file_path) as f:
        return yaml.safe_load(f) or {}


def save_yaml(data: dict, file_path: Path):
    with open(file_path, "w") as f:
        yaml.dump(data, f)


def load_services() -> List[Service]:
    data = load_yaml(SERVICES_FILE)
    return [Service.from_dict(s) for s in data.get("services", [])]


def save_services(services: List[Service]):
    data = {"services": [s.model_dump() for s in services]}
    save_yaml(data, SERVICES_FILE)


def load_devices() -> List[Device]:
    data = load_yaml(DEVICES_FILE)
    return [Device.from_dict(d) for d in data.get("devices", [])]


def save_devices(devices: List[Device]):
    data = {"devices": [d.model_dump() for d in devices]}
    save_yaml(data, DEVICES_FILE)


# ===== SERVICE STATUS CHECKERS =====
def check_docker_container_status(compose_path_yaml: str) -> str:
    """Run docker compose ps and return 'running' if all services are up."""
    try:
        compose_file = Path(compose_path_yaml).parent
        result = subprocess.run(
            ["docker", "compose", "-f", compose_path_yaml, "ps", "--format", "json"],
            cwd=compose_file,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "unknown"
        # docker compose ps output contains "running" for each running container
        return "running" if "running" in result.stdout.lower() else "stopped"
    except Exception:
        return "unknown"


def check_systemd_status(service_name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def check_process_status(pid_file: str) -> str:
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        # psutil not available, just check /proc
        return "running" if Path(f"/proc/{pid}").exists() else "stopped"
    except Exception:
        return "unknown"


def check_http_health(base_url: str, endpoint: Optional[str]) -> bool:
    if not endpoint:
        return True
    try:
        import urllib.request

        url = f"{base_url}{endpoint}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status < 400
    except Exception:
        return False


def get_service_status(service: Service) -> str:
    if service.type == "docker-compose":
        return check_docker_container_status(service.path or "")
    elif service.type == "systemd":
        return check_systemd_status(service.service_name or "")
    elif service.type == "process":
        return check_process_status(service.pid_file)
    elif service.type == "http":
        return (
            "healthy"
            if check_http_health(service.url, service.health_endpoint)
            else "unhealthy"
        )
    return "unknown"


# ===== CONTROL ACTIONS =====
def execute_control(service: Service, action: str) -> None:
    """Run start/stop/restart based on service type."""
    if not action:
        return

    if service.type == "docker-compose":
        compose_path = Path(service.path).parent
        cmd = ["docker", "compose", "-f", service.path, action]
        subprocess.run(cmd, cwd=compose_path, capture_output=True, text=True)
    elif service.type == "systemd":
        subprocess.run(
            ["systemctl", action, service.service_name or ""], capture_output=True
        )
    elif service.type == "process":
        if action == "start":
            subprocess.Popen(service.path.split())
        elif action == "stop":
            try:
                with open(service.pid_file or "") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 9)
            except Exception:
                pass
    elif service.type == "http":
        # No control action for raw HTTP services
        pass


# ===== ENDPOINTS =====
@app.get("/api/services")
async def list_services():
    services = load_services()
    for s in services:
        s.status = get_service_status(s)
    return services


@app.post("/api/services/{service_name}/control")
async def control_service(service_name: str, control: ServiceControl):
    services = load_services()
    service = next((s for s in services if s.name == service_name), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    execute_control(service, control.action)
    return {"status": "success", "action": control.action}


@app.get("/api/devices")
async def list_devices():
    devices = load_devices()
    return devices


@app.post("/api/devices")
async def add_device(device: Device):
    devices = load_devices()
    devices.append(device)
    save_devices(devices)
    return device


@app.delete("/api/devices/<mac>")
async def remove_device(mac: str):
    devices = load_devices()
    devices = [d for d in devices if d.mac != mac]
    save_devices(devices)
    return {"status": "success"}


@app.get("/api/discover")
async def discover_services():
    discovered = []
    search_paths = [
        Path.home() / "dev",
        Path("/opt"),
        Path.home() / ".openclaw",
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue
        for compose_file in search_path.rglob("docker-compose*.yaml"):
            if "node_modules" in str(compose_file):
                continue
            discovered.append(
                {
                    "name": compose_file.parent.name,
                    "type": "docker-compose",
                    "path": str(compose_file),
                }
            )

    # systemd unit discovery
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            if ".service" in line and "loaded" in line:
                unit = line.split()[0].replace(".service", "")
                if unit not in ["docker", "systemd", "getty"]:
                    discovered.append(
                        {"name": unit, "type": "systemd", "service_name": unit}
                    )
    except Exception:
        pass

    return discovered


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
