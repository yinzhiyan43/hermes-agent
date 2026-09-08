import asyncio
import pytest
from fastapi import HTTPException


def test_codex_card_is_official_external_flow():
    from hermes_cli.web_server_oauth import _OAUTH_PROVIDER_CATALOG
    row = next(p for p in _OAUTH_PROVIDER_CATALOG if p['id'] == 'openai-codex')
    assert row['name'] == 'Codex App Server'
    assert row['flow'] == 'external'
    assert row['cli_command'] == 'codex login'
    from hermes_cli.web_routers.oauth import _DEVICE_CODE_STARTERS
    assert 'openai-codex' not in _DEVICE_CODE_STARTERS


def test_codex_status_does_not_read_profile_oauth(monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.web_routers.oauth import _resolve_provider_status
    monkeypatch.setattr(bridge,'auth_status',lambda: {'logged_in':True,'source':'codex-app-server'})
    row = _resolve_provider_status('openai-codex',None)
    assert row['logged_in'] and row['source']=='codex-app-server'
    assert not row['token_preview'] and not row['has_refresh_token']


def test_setting_codex_model_activates_runtime_in_selected_profile(tmp_path,monkeypatch):
    import yaml
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.web_server_config import _apply_main_assignment_sync
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    monkeypatch.setattr(bridge,'auth_status',lambda:{'logged_in':True})
    monkeypatch.setattr(bridge,'list_models',lambda:['account-model'])
    cfg={'model': {'provider':'nous','default':'old','base_url':'https://old.invalid','key_env':'OLD_KEY'}}
    result=_apply_main_assignment_sync(cfg,'openai-codex','account-model','','')
    saved=yaml.safe_load((tmp_path/'config.yaml').read_text())
    assert result['ok']
    assert saved['model']['openai_runtime']=='codex_app_server'
    assert saved['model']['default']=='account-model'
    assert not any(saved['model'].get(k) for k in ('api_key','base_url','key_env','api_mode'))
    assert saved['auxiliary']['background_review']['enabled'] is False


def test_setting_unknown_codex_model_does_not_write(tmp_path,monkeypatch):
    from hermes_cli import codex_app_server_bridge as bridge
    from hermes_cli.web_server_config import _apply_main_assignment_sync
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    monkeypatch.setattr(bridge,'auth_status',lambda:{'logged_in':True})
    monkeypatch.setattr(bridge,'list_models',lambda:['account-model'])
    with pytest.raises(HTTPException):
        _apply_main_assignment_sync({'model':{}},'openai-codex','unknown','','')
    assert not (tmp_path/'config.yaml').exists()
