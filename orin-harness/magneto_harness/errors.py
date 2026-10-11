"""Error types for the Orin harness.

`HarnessError` covers problems the harness itself raises. `ContractError` is a
`ValueError`, matching how the director runtime treats contract validation
failures, so callers can catch it the same way.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for harness failures."""


class ConfigError(HarnessError):
    """Invalid or missing configuration."""


class DeviceError(HarnessError):
    """A physical or simulated device failed."""


class BrainError(HarnessError):
    """The Personal Intelligence brain could not be reached or returned junk."""


class LessonNotFoundError(ConfigError):
    """A requested lesson id is not in the configured catalog."""


class ContractError(ValueError):
    """A payload violates a companion contract boundary."""
