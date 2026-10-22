import factory

from apps.__app__.models import __Model__
from apps.core.tests.factories import UserFactory


class __Model__Factory(factory.django.DjangoModelFactory):
    class Meta:
        model = __Model__

    title = factory.Sequence(lambda n: f"__ModelTitle__ {n}")
    created_by = factory.SubFactory(UserFactory)
