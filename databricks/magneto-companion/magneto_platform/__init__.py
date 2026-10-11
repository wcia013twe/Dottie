"""Explicit service adapters. Importing this package does not authenticate or mutate state."""
from .services import ServiceConfig, Services

__all__ = ["ServiceConfig", "Services"]
