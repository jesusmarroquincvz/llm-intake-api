from unittest.mock import Mock

import phoenix.otel

import intake.tracing


def test_setup_tracing_registers_when_endpoint_set(monkeypatch):
    monkeypatch.setenv("PHOENIX_ENDPOINT", "http://localhost:6006")
    register = Mock()
    monkeypatch.setattr(phoenix.otel, "register", register)

    intake.tracing.setup_tracing()

    register.assert_called_once_with(
        endpoint="http://localhost:6006", project_name="intake-api", auto_instrument=True
    )


def test_setup_tracing_uses_given_project_name(monkeypatch):
    monkeypatch.setenv("PHOENIX_ENDPOINT", "http://localhost:6006")
    register = Mock()
    monkeypatch.setattr(phoenix.otel, "register", register)

    intake.tracing.setup_tracing(project_name="custom-project")

    register.assert_called_once_with(
        endpoint="http://localhost:6006", project_name="custom-project", auto_instrument=True
    )


def test_setup_tracing_does_nothing_when_endpoint_unset(monkeypatch):
    monkeypatch.delenv("PHOENIX_ENDPOINT", raising=False)
    register = Mock()
    monkeypatch.setattr(phoenix.otel, "register", register)

    intake.tracing.setup_tracing()

    register.assert_not_called()


def test_setup_tracing_does_nothing_when_endpoint_empty(monkeypatch):
    monkeypatch.setenv("PHOENIX_ENDPOINT", "")
    register = Mock()
    monkeypatch.setattr(phoenix.otel, "register", register)

    intake.tracing.setup_tracing()

    register.assert_not_called()
