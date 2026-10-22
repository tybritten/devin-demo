from apps.core.registry import OpsAppConfig


class KycConfig(OpsAppConfig):
    name = "apps.kyc"
    label = "kyc"
    verbose_name = "KYC Review"
    nav_label = "KYC Queue"
    nav_url_name = "kyc:queue"
    access_permission = "kyc.view_reviewcase"
    order = 10
