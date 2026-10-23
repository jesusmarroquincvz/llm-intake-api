"""Exceptions raised by the intake package."""


class IntakeError(Exception):
    """Base class for every error raised by intake."""


class ValidationError(IntakeError):
    """The caller passed a value the API cannot accept."""


class AgentError(IntakeError):
    """An agent could not produce a valid decision (bad model output, unknown label)."""
