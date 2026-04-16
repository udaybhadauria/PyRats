"""
System API Endpoints
Replaces C-server endpoints: CheckForSwUpgrade, UpdateSoftware, environment toggle.
Preserves exact JSON response shapes consumed by the legacy frontend UI.
"""

import asyncio
import subprocess
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from app.settings import settings
from app.utils import logger

router = APIRouter(prefix="/api/system", tags=["system"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_repourl() -> dict:
    """Parse repourl.txt into a dict of key=value pairs."""
    out = {}
    p = settings.REPO_URL_CONFIG.resolve()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def _current_version() -> str:
    """Get current git tag via 'git describe --tags', fallback to version file."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback: read /var/tmp/sw_version.txt if present
    sw_file = Path("/var/tmp/sw_version.txt")
    if sw_file.exists():
        ver = sw_file.read_text().strip()
        if ver:
            return ver
    return "unknown"


def _is_prod() -> bool:
    return not Path("/var/tmp/dev_environment.txt").exists()


# ---------------------------------------------------------------------------
# GET /api/system/checkForSwUpgrade
# Legacy UI calls this to show latestVersion / currentVersion badge.
# ---------------------------------------------------------------------------

@router.get("/checkForSwUpgrade")
async def check_for_sw_upgrade():
    """
    Check GitHub for the latest release tag and compare with current version.
    Preserves exact response shape from legacy RATS.c CheckForSwUpgrade():
        { "status": "success", "environment": "Prod|Dev",
          "latestVersion": "v1.2.3", "currentVersion": "v1.2.2" }
    """
    urls = _read_repourl()
    is_prod = _is_prod()
    check_url = urls.get("URL_RELEASE_CHECK") if is_prod else urls.get("DEV_URL_RELEASE_CHECK", "")
    current = _current_version()

    if not check_url:
        return {
            "status": "error",
            "environment": "Prod" if is_prod else "Dev",
            "latestVersion": "unknown",
            "currentVersion": current,
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(check_url, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            data = resp.json()
            latest = data.get("tag_name", "unknown")
    except Exception as exc:
        logger.warning(f"GitHub release check failed: {exc}")
        return {
            "status": "error",
            "environment": "Prod" if is_prod else "Dev",
            "latestVersion": "unknown",
            "currentVersion": current,
            "error": str(exc),
        }

    return {
        "status": "success",
        "environment": "Prod" if is_prod else "Dev",
        "latestVersion": latest,
        "currentVersion": current,
    }


# ---------------------------------------------------------------------------
# POST /api/system/updateSoftware
# Triggers backend/Utility/sw_dl/software_dl script asynchronously.
# ---------------------------------------------------------------------------

@router.post("/updateSoftware")
async def update_software():
    """
    Trigger software download and migration.
    Equivalent to legacy /UpdateSoftware POST endpoint in RATS.c.
    Runs software_dl asynchronously so the HTTP call returns immediately.
    """
    sw_dl_dir = (settings.LEGACY_UTILITY_DIR / "sw_dl").resolve()
    sw_dl_bin = sw_dl_dir / "software_dl"

    if not sw_dl_bin.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="software_dl binary not found in Utility/sw_dl/"
        )

    try:
        asyncio.create_task(
            _run_shell(f"cd '{sw_dl_dir}' && ./software_dl &")
        )
        return {"status": "accepted", "message": "Software update initiated"}
    except Exception as exc:
        logger.error(f"Failed to start software update: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# POST /api/system/environment
# Toggle Prod/Dev environment flag (mirrors legacy check_environment() logic).
# ---------------------------------------------------------------------------

@router.post("/environment")
async def set_environment(body: dict):
    """
    Set environment to Prod or Dev.
    Body: { "environment": "Prod" | "Dev" }
    """
    env = body.get("environment", "Prod")
    flag = Path("/var/tmp/dev_environment.txt")
    try:
        if env == "Dev":
            flag.touch(exist_ok=True)
        else:
            if flag.exists():
                flag.unlink()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Cannot write to /var/tmp/ – run as root or sudo")

    return {"status": "success", "environment": env}


# ---------------------------------------------------------------------------
# GET /api/system/environment
# ---------------------------------------------------------------------------

@router.get("/environment")
async def get_environment():
    """Return current environment setting."""
    return {"environment": "Prod" if _is_prod() else "Dev"}


# ---------------------------------------------------------------------------
# Internal async shell helper
# ---------------------------------------------------------------------------

async def _run_shell(cmd: str):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
