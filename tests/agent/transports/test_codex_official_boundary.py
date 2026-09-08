import pytest

@pytest.fixture(autouse=True)
def official(tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    (tmp_path/'config.yaml').write_text('model:\n  provider: openai-codex\n  openai_runtime: codex_app_server\n')

@pytest.mark.parametrize('requested',[None,'auto','openai-codex'])
def test_skip_oauth_and_pool(monkeypatch,requested):
    from hermes_cli import runtime_provider as rp
    def forbidden(*a,**kw): raise AssertionError('Credential access forbidden')
    monkeypatch.setattr(rp,'load_pool',forbidden)
    monkeypatch.setattr(rp,'resolve_codex_runtime_credentials',forbidden)
    assert rp.resolve_runtime_provider(requested=requested)['api_mode']=='codex_app_server'

@pytest.mark.parametrize('fn',['_read_codex_tokens','_import_codex_cli_tokens','resolve_codex_runtime_credentials','_pool_codex_access_token','_codex_device_code_login'])
def test_auth_is_managed(fn):
    from hermes_cli import auth_codex
    from hermes_cli.auth import AuthError
    with pytest.raises(AuthError,match='App Server manages'):
        getattr(auth_codex,fn)()

def test_auxiliary_cannot_downgrade():
    from agent.auxiliary_client import resolve_provider_client
    with pytest.raises(ValueError,match='session runtime'):
        resolve_provider_client('openai-codex','gpt-5.6-sol')

def test_review_disabled():
    from agent.background_review import load_background_review_settings
    assert load_background_review_settings()==(False,{})

def test_account_rpc(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from agent.account_usage import _fetch_codex_account_usage
    calls=[]
    def rpc(method,params):
        calls.append(method)
        return {'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':20,'windowDurationMins':300,'resetsAt':2000000000}}}}
    monkeypatch.setattr(bridge,'request',rpc)
    snapshot=_fetch_codex_account_usage(api_key='unused')
    assert snapshot.source=='codex-app-server'
    assert snapshot.windows[0].used_percent==20
    assert calls==['account/rateLimits/read']

def test_catalog_rpc_failure_no_fallback(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.codex_models import get_codex_model_ids
    def fail(): raise RuntimeError('RPC unavailable')
    monkeypatch.setattr(bridge,'list_models',fail)
    with pytest.raises(RuntimeError,match='RPC unavailable'): get_codex_model_ids()

def test_picker_uses_official_login_without_hermes_tokens(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.model_switch_providers import _overlay_has_creds
    monkeypatch.setattr(bridge, 'auth_status', lambda: {'logged_in': True})
    assert _overlay_has_creds(None, 'openai-codex', 'openai-codex', None)


def test_picker_never_uses_stale_cache(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli import models
    monkeypatch.setattr(bridge, 'list_models', lambda: ['account-model'])
    assert models.cached_provider_model_ids('openai-codex') == ['account-model']


def test_official_validation_rejects_guessed_models(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.models_validate import validate_requested_model
    monkeypatch.setattr(bridge, 'list_models', lambda: ['account-model'])
    assert validate_requested_model('account-model', 'openai-codex')['accepted']
    assert not validate_requested_model('guessed-model', 'openai-codex')['accepted']


def test_model_change_reopens_existing_binding(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from agent.codex_runtime import _ensure_codex_session
    from agent.transports import codex_app_server_session as session_module
    from tests.agent.transports.test_codex_session_binding import Client
    real = session_module.CodexAppServerSession
    def factory(**kwargs):
        return real(**kwargs, client_factory=Client)
    monkeypatch.setattr(session_module, 'CodexAppServerSession', factory)
    agent = SimpleNamespace(model='model-one', session_id='model-switch-test', session_cwd=str(tmp_path))
    _ensure_codex_session(agent)
    first = agent._codex_session
    thread_id = first.ensure_started()
    agent.model = 'model-two'
    _ensure_codex_session(agent)
    assert agent._codex_session is not first
    assert agent._codex_session.ensure_started() == thread_id
    method, params = agent._codex_session._client.requests[0]
    assert method == 'thread/resume' and params['model'] == 'model-two'
    agent._codex_session.close()


@pytest.mark.parametrize("legacy_mode", [None, "codex_responses"])
def test_fresh_and_legacy_profiles_always_use_app_server(monkeypatch, legacy_mode):
    from hermes_cli import runtime_provider as rp
    from hermes_cli.providers import determine_api_mode
    monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "openai-codex", "openai_runtime": legacy_mode})
    runtime = rp.resolve_runtime_provider(requested="openai-codex")
    assert runtime["api_mode"] == "codex_app_server"
    assert determine_api_mode("openai-codex", runtime["base_url"]) == "codex_app_server"


@pytest.mark.parametrize("legacy_mode", [None, "codex_responses", "chat_completions"])
def test_restored_agent_cannot_restore_legacy_codex_transport(legacy_mode):
    from types import SimpleNamespace
    from agent.agent_init import _resolve_api_mode

    agent = SimpleNamespace(provider="openai-codex", _base_url_hostname="chatgpt.com",
                            _base_url_lower="https://chatgpt.com/backend-api/codex")
    _resolve_api_mode(agent, legacy_mode, "openai-codex", agent._base_url_lower)
    assert agent.api_mode == "codex_app_server"
