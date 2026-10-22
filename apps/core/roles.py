from django.contrib.auth.models import Group, Permission


def sync_roles(app_label, roles):
    """Create each group in `roles` ({group name: [codenames]}) and grant its permissions."""
    for group_name, codenames in roles.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        perms = Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
        group.permissions.add(*perms)
