"""Temporary shim: settings moved to settings package.
Keep for backward compatibility; import from settings.base by default.
"""

from .settings import base as _base  # noqa: F401