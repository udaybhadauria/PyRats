"""API Routers and endpoints"""

from .devices import router as devices_router
from .tests import router as tests_router
from .health import router as health_router
from .system import router as system_router

__all__ = ["devices_router", "tests_router", "health_router", "system_router"]
