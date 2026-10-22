import re
import uuid

from .context import _current_request

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class AuditContextMiddleware:
    """Tag each request with an ID (reusing a sane upstream X-Request-ID) and expose it to audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request.request_id = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        token = _current_request.set(request)
        try:
            response = self.get_response(request)
        finally:
            _current_request.reset(token)
        response["X-Request-ID"] = request.request_id
        return response
