# src/services/automation/__init__.py

"""Система автоматических триггеров."""

from src.services.automation.engine import emit_automation_event

__all__ = ['emit_automation_event']
