from .models import __Model__


def tile(user):
    """Home-page tile. Only called for users holding the app's `access_permission`."""
    open_records = __Model__.objects.open()
    return {
        "title": "__Title__",
        "description": "Describe what this app is for in one line.",
        "url_name": "__app__:list",
        "stats": [
            ("Open", open_records.count()),
            ("Mine", open_records.filter(owner=user).count()),
        ],
    }
