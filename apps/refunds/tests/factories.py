from decimal import Decimal

import factory

from apps.core.tests.factories import UserFactory
from apps.refunds.models import Refund


class RefundFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Refund

    customer_name = factory.Faker("name")
    order_ref = factory.Sequence(lambda n: f"ORD-{n}")
    amount = Decimal("100.00")
    reason = Refund.Reason.BILLING_ERROR
    requested_by = factory.SubFactory(UserFactory)
