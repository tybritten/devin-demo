"""Access-boundary checks over every URL in the project.

New URLs are covered automatically. A URL that is reachable without login, or with login
but no app permission, must be listed below on purpose, or this suite fails.
"""

import re

import pytest
from django.contrib.auth.models import Group
from django.urls import URLPattern, URLResolver, get_resolver

from apps.core.registry import ops_apps
from apps.core.tests.factories import UserFactory

# Reachable without a session. Value: the status an anonymous GET must return.
PUBLIC = {"healthz": 200, "login": 200, "flags:api_flag_list": 401, "flags:api_flag_evaluate": 401}
# Any logged-in user may open these; they show only what the user's own roles allow.
ANY_AUTHENTICATED = {"home", "logout"}
SKIP_NAMESPACES = {"admin"}  # Django admin enforces is_staff + model permissions itself.

DENIED = {403, 405}
ARG = re.compile(r"<(?:(\w+):)?(\w+)>")
DUMMY = {
    "int": "999999",
    "slug": "x",
    "str": "x",
    "path": "x",
    "uuid": "00000000-0000-0000-0000-000000000000",
}


def _walk(patterns, prefix="", namespace=None):
    for p in patterns:
        if isinstance(p, URLResolver):
            ns = p.namespace or namespace
            if ns in SKIP_NAMESPACES:
                continue
            full_ns = f"{namespace}:{p.namespace}" if namespace and p.namespace else ns
            yield from _walk(p.url_patterns, prefix + str(p.pattern), full_ns)
        elif isinstance(p, URLPattern) and p.name:
            route = prefix + str(p.pattern)
            url = "/" + ARG.sub(lambda m: DUMMY[m.group(1) or "str"], route).lstrip("^").rstrip("$")
            name = f"{namespace}:{p.name}" if namespace else p.name
            yield name, url, namespace


ROUTES = sorted(set(_walk(get_resolver().url_patterns)))
APP_LABELS = {app.label for app in ops_apps()}


def _ids(routes):
    return [name for name, _, _ in routes]


def test_every_url_is_classified():
    unclassified = [
        name
        for name, _, ns in ROUTES
        if ns not in APP_LABELS and name not in PUBLIC and name not in ANY_AUTHENTICATED
    ]
    assert not unclassified, (
        f"URLs outside any ops app need an explicit access rule: {unclassified}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("name", "url", "ns"), ROUTES, ids=_ids(ROUTES))
def test_anonymous_is_redirected_to_login(client, name, url, ns):
    if name in PUBLIC:
        assert client.get(url).status_code == PUBLIC[name]
        return
    for method in (client.get, client.post):
        resp = method(url)
        assert resp.status_code == 302, f"{name} {method.__name__} -> {resp.status_code}"
        assert resp["Location"].startswith("/accounts/login/")


APP_ROUTES = [r for r in ROUTES if r[2] in APP_LABELS and r[0] not in PUBLIC]


@pytest.mark.django_db
@pytest.mark.parametrize(("name", "url", "ns"), APP_ROUTES, ids=_ids(APP_ROUTES))
def test_user_without_roles_is_denied(client, name, url, ns):
    client.force_login(UserFactory(username="norole"))
    for method in (client.get, client.post):
        status = method(url).status_code
        assert status in DENIED, f"{name} {method.__name__} -> {status}"


def _foreign_roles():
    for app in ops_apps():
        for role in app.roles():
            yield app.label, role


@pytest.mark.django_db
@pytest.mark.parametrize(("label", "role"), list(_foreign_roles()))
def test_roles_do_not_grant_access_to_other_apps(client, label, role):
    user = UserFactory(username="scoped")
    user.groups.add(Group.objects.get(name=role))
    client.force_login(user)
    leaks = []
    for name, url, ns in APP_ROUTES:
        if ns == label:
            continue
        for method in (client.get, client.post):
            status = method(url).status_code
            if status not in DENIED:
                leaks.append(f"{name} {method.__name__} -> {status}")
    assert not leaks, f"{role!r} reaches other apps: {leaks}"
