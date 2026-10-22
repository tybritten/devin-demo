import factory

from apps.core.tests.factories import UserFactory  # noqa: F401  (re-exported)
from apps.kyc.models import Customer, ReviewCase


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    legal_name = factory.Faker("name")
    external_ref = factory.Sequence(lambda n: f"CRM-{n:05d}")
    country = "US"


class ReviewCaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewCase

    customer = factory.SubFactory(CustomerFactory)
