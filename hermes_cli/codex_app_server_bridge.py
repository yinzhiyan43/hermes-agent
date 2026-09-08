"""Account/catalog operations for the official Codex App Server runtime.

Authentication stays inside the official subprocess. RPC failures propagate;
there is deliberately no fallback to Hermes OAuth or private HTTP endpoints.
"""
def is_enabled(config=None):
    """This distribution always delegates Codex authentication and transport to its CLI.

    Keep the optional config argument for callers shared with upstream. Legacy
    profile flags cannot re-enable direct Codex OAuth in this distribution.
    """
    return True


def request(method, params):
    from agent.transports.codex_app_server import CodexAppServerClient
    client = CodexAppServerClient()
    try:
        client.initialize()
        return client.request(method, params, timeout=30)
    finally:
        client.close()


def list_models():
    from agent.transports.codex_app_server import CodexAppServerClient
    client = CodexAppServerClient()
    models, seen_cursors = [], set()
    cursor = None
    try:
        client.initialize()
        while True:
            params = {"limit": 100, "includeHidden": False}
            if cursor:
                params["cursor"] = cursor
            result = client.request("model/list", params, timeout=30)
            for item in result["data"]:
                model = item.get("model") or item.get("id")
                if isinstance(model, str) and model and not item.get("hidden") and model not in models:
                    models.append(model)
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if cursor in seen_cursors:
                raise ValueError("Codex model catalog returned a repeated cursor.")
            seen_cursors.add(cursor)
        if not models:
            raise ValueError("Codex App Server returned no available models.")
        return models
    finally:
        client.close()


def auth_status():
    try:
        result = request("account/read", {"refreshToken": False})
        account = result.get("account") or {}
        return {
            "logged_in": bool(account), "source": "codex-app-server",
            "auth_mode": account.get("type"), "plan": account.get("planType"),
        }
    except Exception:
        return {"logged_in": False, "source": "codex-app-server",
                "error": "Official Codex account status unavailable. Check `codex login status`."}


def select_model(current_model):
    from hermes_cli.auth import _prompt_model_selection
    from hermes_cli.config import load_config, save_config
    status = auth_status()
    if not status.get("logged_in"):
        print(status.get("error") or "Sign in using `codex login`, then retry.")
        return
    models = list_models()
    selected = _prompt_model_selection(models, current_model=current_model)
    if not selected:
        print("No change.")
        return
    if selected not in models:
        raise ValueError("Choose a model returned by the official Codex model catalog.")
    config = load_config()
    block = config.setdefault("model", {})
    block.update(default=selected, provider="openai-codex", openai_runtime="codex_app_server")
    block.pop("base_url", None)
    block.pop("api_key", None)
    save_config(config)
    print(f"Default model set to: {selected} (via official Codex App Server)")


def rate_windows(payload):
    """Prefer per-limit buckets; preserve unknown window fields as unknown."""
    buckets = payload.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict) or not buckets:
        legacy = payload.get("rateLimits")
        buckets = {"codex": legacy} if isinstance(legacy, dict) else {}
    for name, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        label = bucket.get("limitName") or name
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if isinstance(window, dict):
                yield f"{label} / {kind}", window


def redeem_reset(*, force=False):
    """User-triggered redemption only. Never retry an uncertain consumption."""
    import uuid
    from agent.account_usage import CodexResetRedeemResult
    request_id = None
    try:
        payload = request("account/rateLimits/read", {})
        available = (payload.get("rateLimitResetCredits") or {}).get("availableCount")
        if not isinstance(available, int):
            return CodexResetRedeemResult("unavailable", "Reset credit count unavailable; nothing consumed.")
        if available <= 0:
            return CodexResetRedeemResult("no_credits_banked", "No banked reset credits.")
        exhausted = any(isinstance(w.get("usedPercent"), (int, float)) and w["usedPercent"] >= 100
                        for _, w in rate_windows(payload))
        if not exhausted and not force:
            return CodexResetRedeemResult("not_exhausted", "No confirmed exhausted window. Use /usage reset --force to redeem anyway.", available)
        request_id = str(uuid.uuid4())
        body = request("account/rateLimitResetCredit/consume", {"idempotencyKey": request_id})
        statuses = {"reset": "reset", "alreadyRedeemed": "already_redeemed",
                    "nothingToReset": "nothing_to_reset", "noCredit": "no_credit"}
        status = statuses.get(body.get("outcome"), "unavailable")
        # Consumption responses do not include refreshed limits. Keep a confirmed
        # outcome even when the subsequent read fails; never repeat consumption.
        try:
            refreshed = request("account/rateLimits/read", {})
            count = (refreshed.get("rateLimitResetCredits") or {}).get("availableCount")
        except Exception:
            count = None
        suffix = " Remaining credits unavailable; check /usage." if count is None else ""
        return CodexResetRedeemResult(status, f"Codex reset result: {status}." + suffix,
            available_count=count if isinstance(count, int) else 0)
    except Exception:
        message = "Official Codex reset request unavailable; no automatic retry."
        if request_id:
            message += f" Outcome uncertain; check usage before another redemption. Request ID: {request_id}"
        return CodexResetRedeemResult("unavailable", message)
