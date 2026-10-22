"""HTTP session shared by every connector: timeouts are set per request, retries here."""

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RETRY_STATUSES = (429, 500, 502, 503, 504)


def build_session(retries=None):
    """Retries idempotent reads on throttling and server errors, honouring Retry-After.

    Writes are never retried automatically: a POST that timed out may still have succeeded.
    """
    retry = Retry(
        total=settings.INTEGRATIONS_HTTP_RETRIES if retries is None else retries,
        backoff_factor=settings.INTEGRATIONS_HTTP_BACKOFF,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "opsapps-integrations"
    return session
