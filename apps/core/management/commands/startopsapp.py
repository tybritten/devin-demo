"""Generate a new ops app under apps/<label> from apps/core/app_template."""

import importlib.util
import keyword
import re
import shutil
import subprocess
import sys
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "app_template"
LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")
MODEL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
OPS_APPS_RE = re.compile(r"^OPS_APPS = \[\n(?P<body>(?:    .*\n)*)\]", re.MULTILINE)


def camel(label):
    return "".join(part.capitalize() for part in label.split("_"))


def humanize(model):
    return re.sub(r"(?<!^)(?=[A-Z])", " ", model).lower()


class Command(BaseCommand):
    help = (
        "Create apps/<label> with a model, audited services, roles, views, templates, admin "
        "and tests; register it in OPS_APPS and make its first migration."
    )

    def add_arguments(self, parser):
        parser.add_argument("label", help="App label in snake_case, e.g. vendor_onboarding.")
        parser.add_argument("--model", help="Main model class, e.g. VendorRequest.")
        parser.add_argument("--title", help="Human name shown in the UI, e.g. 'Vendor Onboarding'.")
        parser.add_argument(
            "--no-register",
            action="store_true",
            help="Only write files; don't edit OPS_APPS or run makemigrations.",
        )

    def handle(self, label, model=None, title=None, no_register=False, **options):
        model = model or camel(label)
        title = title or label.replace("_", " ").title()
        target = Path(settings.BASE_DIR) / "apps" / label
        self._validate(label, model, target)

        tokens = {
            "__ModelTitle__": humanize(model).capitalize(),
            "__model_title__": humanize(model),
            "__Model__": model,
            "__model__": model.lower(),
            "__Title__": title,
            "__App__": camel(label),
            "__app__": label,
        }
        self._render(target, tokens)
        self._tidy(target)
        self.stdout.write(self.style.SUCCESS(f"Created {target.relative_to(settings.BASE_DIR)}/"))
        if no_register:
            return
        self._register(label)
        self._run("manage.py", "makemigrations", label)
        self.stdout.write(
            self.style.SUCCESS(f"Registered apps.{label} in OPS_APPS and made its migration.")
        )
        self.stdout.write(
            f"Next: `manage.py migrate`, `pytest apps/{label}`, then replace the placeholder "
            f"fields in apps/{label}/models.py with the real ones."
        )

    def _validate(self, label, model, target):
        if not LABEL_RE.match(label) or keyword.iskeyword(label) or "__" in label:
            raise CommandError("Label must be snake_case, e.g. vendor_onboarding.")
        if any(c.label == label for c in apps.get_app_configs()):
            raise CommandError(f"An app labelled {label!r} is already installed.")
        if target.exists():
            raise CommandError(f"{target} already exists.")
        if not MODEL_RE.match(model) or keyword.iskeyword(model):
            raise CommandError("Model must be CamelCase, e.g. VendorRequest.")

    def _render(self, target, tokens):
        def sub(text):
            for token, value in tokens.items():
                text = text.replace(token, value)
            return text

        try:
            for src in sorted(TEMPLATE_DIR.rglob("*.tpl")):
                dest = target / sub(str(src.relative_to(TEMPLATE_DIR)))[: -len(".tpl")]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(sub(src.read_text()))
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def _tidy(self, target):
        """Sort imports and wrap long lines so the generated code passes CI's ruff checks."""
        if importlib.util.find_spec("ruff"):
            self._run("-m", "ruff", "format", "--quiet", str(target), check=False)
            self._run("-m", "ruff", "check", "--fix", "--quiet", str(target), check=False)

    def _register(self, label):
        path = Path(settings.BASE_DIR) / "config" / "settings.py"
        source = path.read_text()
        match = OPS_APPS_RE.search(source)
        if not match:
            raise CommandError(f"Couldn't find OPS_APPS in {path}; add 'apps.{label}' by hand.")
        entry = f'    "apps.{label}",\n'
        path.write_text(source[: match.end("body")] + entry + source[match.end("body") :])

    def _run(self, *args, check=True):
        subprocess.run([sys.executable, *args], cwd=settings.BASE_DIR, check=check)  # noqa: S603
