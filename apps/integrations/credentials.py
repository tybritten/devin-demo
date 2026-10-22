"""Microsoft Entra ID app-only (client credentials) tokens, cached in-process until expiry."""

import os
import threading
import time

import requests
from django.conf import settings

from .errors import CredentialError

EXPIRY_MARGIN = 60  # seconds: refresh a little before Entra's expiry
_cache = {}
_lock = threading.Lock()


def clear_cache():
    with _lock:
        _cache.clear()


def get_token(system, scope, session):
    key = (system.tenant_id, system.client_id, system.client_secret_env, scope)
    with _lock:
        cached = _cache.get(key)
    if cached and cached[1] > time.monotonic() + EXPIRY_MARGIN:
        return cached[0]

    secret = os.environ.get(system.client_secret_env)
    if not secret:
        raise CredentialError(
            f"{system.slug}: environment variable {system.client_secret_env} is not set."
        )
    url = f"{settings.ENTRA_AUTHORITY_HOST.rstrip('/')}/{system.tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": system.client_id,
        "client_secret": secret,
        "scope": scope,
    }
    try:
        resp = session.post(url, data=data, timeout=system.timeout_seconds)
    except requests.RequestException as exc:
        raise CredentialError(
            f"{system.slug}: token request failed ({exc.__class__.__name__})"
        ) from exc
    if resp.status_code != 200:
        raise CredentialError(
            f"{system.slug}: Entra rejected the token request ({resp.status_code} "
            f"{_entra_error(resp)})"
        )
    body = resp.json()
    token = body["access_token"]
    with _lock:
        _cache[key] = (token, time.monotonic() + int(body.get("expires_in", 3600)))
    return token


def _entra_error(resp):
    """Entra's error code and first line (e.g. AADSTS7000215), which never echo the secret."""
    try:
        body = resp.json()
    except ValueError:
        return ""
    description = (body.get("error_description") or "").splitlines()[:1]
    return " ".join([body.get("error", ""), *description]).strip()[:300]
