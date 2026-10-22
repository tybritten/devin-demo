from apps.core.registry import OpsAppConfig


class __App__Config(OpsAppConfig):
    name = "apps.__app__"
    label = "__app__"
    verbose_name = "__Title__"
    nav_url_name = "__app__:list"
    access_permission = "__app__.view___model__"
