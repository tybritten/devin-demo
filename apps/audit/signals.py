"""Automatic audit entries: model changes in ops apps and auth, permission changes, logins."""

import hashlib
import json

from django.contrib.auth import get_user_model, user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth.models import Group
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save

from apps.core.registry import ops_apps

from .log import Action, record

MASKED_FIELDS = {"password", "token_hash"}
IGNORED_FIELDS = {"last_login", "last_used_at", "updated_at"}
MASK = "********"


def audited_models():
    models = [get_user_model(), Group]
    for app in ops_apps():
        if app.label != "audit":
            models.extend(app.get_models())
    return models


def _snapshot(instance):
    values = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        value = field.value_from_object(instance)
        if field.name in MASKED_FIELDS:
            # Hash-of-a-hash fingerprint: shows that it changed, reveals nothing usable.
            value = f"{MASK}{hashlib.sha256(str(value).encode()).hexdigest()[:8]}" if value else ""
        values[field.attname] = json.loads(json.dumps(value, cls=DjangoJSONEncoder, default=str))
    return values


def _pre_save(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding or instance.pk is None:
        instance._audit_before = None
        return
    old = sender._default_manager.filter(pk=instance.pk).first()
    instance._audit_before = _snapshot(old) if old else None


def _post_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    after = _snapshot(instance)
    if created:
        record(Action.CREATE, obj=instance, changes={"fields": after})
        return
    before = getattr(instance, "_audit_before", None) or {}
    diff = {k: [before.get(k), v] for k, v in after.items() if before.get(k) != v}
    if diff:
        record(Action.UPDATE, obj=instance, changes={"fields": diff})


def _post_delete(sender, instance, **kwargs):
    record(Action.DELETE, obj=instance, changes={"fields": _snapshot(instance)})


def _m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == "pre_clear":
        related = getattr(instance, _accessor(sender, instance, model)).all()
        instance._audit_cleared = [str(o) for o in related]
        return
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if action == "post_clear":
        names = getattr(instance, "_audit_cleared", [])
    else:
        if not pk_set:
            return
        names = [str(o) for o in model._default_manager.filter(pk__in=pk_set)]
    if not names:
        return
    record(
        Action.PERMISSION_CHANGE,
        obj=instance,
        changes={
            "relation": _accessor(sender, instance, model),
            "op": action.removeprefix("post_"),
            "objects": sorted(names),
        },
    )


def _accessor(through, instance, model):
    """Name of the m2m accessor on `instance` that points at `model` via `through`."""
    for field in instance._meta.get_fields():
        if field.many_to_many and getattr(field, "related_model", None) is model:
            remote = getattr(field, "remote_field", None)
            through_model = getattr(field, "through", None) or getattr(remote, "through", None)
            if through_model is through:
                return field.get_accessor_name() if field.auto_created else field.name
    return through._meta.model_name


def _logged_in(sender, request, user, **kwargs):
    record(Action.LOGIN, actor=user, request=request)


def _logged_out(sender, request, user, **kwargs):
    record(Action.LOGOUT, actor=user, request=request)


def _login_failed(sender, credentials, request=None, **kwargs):
    username = str(credentials.get("username", ""))[:150]
    record(Action.LOGIN_FAILED, request=request, changes={"username": username})


def connect():
    for model in audited_models():
        uid = f"audit:{model._meta.label}"
        pre_save.connect(_pre_save, sender=model, dispatch_uid=f"{uid}:pre")
        post_save.connect(_post_save, sender=model, dispatch_uid=f"{uid}:post")
        post_delete.connect(_post_delete, sender=model, dispatch_uid=f"{uid}:del")
    User = get_user_model()
    for through in (User.groups.through, User.user_permissions.through, Group.permissions.through):
        m2m_changed.connect(_m2m_changed, sender=through, dispatch_uid=f"audit:m2m:{through}")
    user_logged_in.connect(_logged_in, dispatch_uid="audit:login")
    user_logged_out.connect(_logged_out, dispatch_uid="audit:logout")
    user_login_failed.connect(_login_failed, dispatch_uid="audit:login_failed")
