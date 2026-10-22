import factory
from django.contrib.auth import get_user_model

from apps.kyc.models import Customer, ReviewCase


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ["username"]

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.django.Password("pw")


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
