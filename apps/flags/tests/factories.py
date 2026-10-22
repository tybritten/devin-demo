import factory

from apps.flags.models import FeatureFlag


class FlagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FeatureFlag

    key = factory.Sequence(lambda n: f"feature.flag_{n}")
    name = factory.Faker("sentence", nb_words=3)
