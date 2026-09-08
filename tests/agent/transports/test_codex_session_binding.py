"""Keep the official Codex thread when a Hermes conversation is reopened."""
import json

import pytest

from agent.transports.codex_app_server_session import CodexAppServerSession
from agent.transports.codex_app_server import CodexAppServerError


class Client:
    def __init__(self, **kwargs):
        self.requests = []

    def initialize(self, **kwargs):
        return {}

    def request(self, method, params, **kwargs):
        self.requests.append((method, params))
        return {"thread": {"id": params.get("threadId", "codex-thread-test")}}

    def close(self):
        pass


def test_reopen_resumes_saved_thread_and_forwards_model(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    first = CodexAppServerSession(hermes_session_id="hermes-one", model="chosen-model", client_factory=Client)
    original_id = first.ensure_started()
    assert first._client.requests == [("thread/start", {"cwd": first._cwd, "model": "chosen-model"})]
    first.close()
    second = CodexAppServerSession(hermes_session_id="hermes-one", client_factory=Client)
    assert second.ensure_started() == original_id
    assert second._client.requests[0][0] == "thread/resume"
    assert second._client.requests[0][1]["threadId"] == original_id
    assert second.ensure_started() == original_id
    assert len(second._client.requests) == 1


def test_different_session_does_not_inherit_thread(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    first = CodexAppServerSession(hermes_session_id="../one", client_factory=Client)
    first.ensure_started()
    second = CodexAppServerSession(hermes_session_id="two", client_factory=Client)
    second.ensure_started()
    assert second._client.requests[0][0] == "thread/start"
    assert len(list((tmp_path / "codex-sessions").glob("*.json"))) == 2


def test_failed_resume_does_not_discard_binding(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    first = CodexAppServerSession(hermes_session_id="one", client_factory=Client)
    first.ensure_started()
    before = first._binding_path.read_bytes()

    class FailingClient(Client):
        def request(self, method, params, **kwargs):
            self.requests.append((method, params))
            raise CodexAppServerError(-1, "resume unavailable")

    second = CodexAppServerSession(hermes_session_id="one", client_factory=FailingClient)
    with pytest.raises(CodexAppServerError):
        second.ensure_started()
    assert [m for m, _ in second._client.requests] == ["thread/resume"]
    assert first._binding_path.read_bytes() == before


def test_bad_binding_fails_instead_of_starting_new_thread(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    session = CodexAppServerSession(hermes_session_id="one", client_factory=Client)
    session._binding_path.parent.mkdir()
    session._binding_path.write_text(json.dumps({"thread_id": None}))
    with pytest.raises(ValueError, match="refusing to discard context"):
        session.ensure_started()
    assert session._client.requests == []


def test_official_runtime_does_not_resolve_hermes_oauth(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model:\n  provider: openai-codex\n  openai_runtime: codex_app_server\n")
    from hermes_cli import runtime_provider as rp
    def forbidden(*args, **kwargs):
        raise AssertionError("Hermes OAuth must not be used by official App Server")
    monkeypatch.setattr(rp, "resolve_codex_runtime_credentials", forbidden)
    result = rp.resolve_runtime_provider(requested="openai-codex")
    assert result["api_mode"] == "codex_app_server"
    assert result["source"] == "codex-app-server"
