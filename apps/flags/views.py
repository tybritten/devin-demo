from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from . import services
from .forms import CommentOnlyForm, FlagFilterForm, FlagForm
from .models import FeatureFlag

FORM_FIELDS = ["name", "description", "owner", "enabled", "rollout_percentage", "targets"]
STATE_FILTERS = {
    "on": Q(is_archived=False, enabled=True, rollout_percentage__gte=100),
    "partial": Q(is_archived=False, enabled=True, rollout_percentage__lt=100),
    "off": Q(is_archived=False, enabled=False),
    "archived": Q(is_archived=True),
}


def _form_errors(request, exc):
    for msg in exc.messages:
        messages.error(request, msg)


class FlagListView(PermissionRequiredMixin, ListView):
    permission_required = "flags.view_featureflag"
    template_name = "flags/flag_list.html"
    context_object_name = "flags"
    paginate_by = 50

    def get_queryset(self):
        self.filter_form = FlagFilterForm(self.request.GET)
        qs = FeatureFlag.objects.select_related("owner")
        data = self.filter_form.cleaned_data if self.filter_form.is_valid() else {}
        qs = qs.filter(STATE_FILTERS.get(data.get("state"), Q(is_archived=False)))
        if q := (data.get("q") or "").strip():
            qs = qs.filter(Q(key__icontains=q) | Q(name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        return super().get_context_data(filter_form=self.filter_form, **kwargs)


@permission_required("flags.add_featureflag", raise_exception=True)
def flag_create(request):
    form = FlagForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            flag = services.create_flag(
                actor=request.user,
                key=data["key"],
                comment=data["comment"],
                **{f: data[f] for f in FORM_FIELDS},
            )
        except ValidationError as exc:
            _form_errors(request, exc)
        else:
            messages.success(request, f"Created {flag.key}.")
            return redirect(flag)
    return render(request, "flags/flag_form.html", {"form": form})


@permission_required("flags.view_featureflag", raise_exception=True)
def flag_detail(request, pk):
    flag = get_object_or_404(FeatureFlag.objects.select_related("owner"), pk=pk)
    can_edit = request.user.has_perm("flags.change_featureflag") and not flag.is_archived
    form = FlagForm(instance=flag) if can_edit else None
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = FlagForm(request.POST, instance=FeatureFlag.objects.get(pk=pk))
        if form.is_valid():
            data = form.cleaned_data
            try:
                services.update_flag(
                    flag,
                    actor=request.user,
                    comment=data["comment"],
                    **{f: data[f] for f in FORM_FIELDS},
                )
            except ValidationError as exc:
                _form_errors(request, exc)
            else:
                messages.success(request, f"Saved {flag.key}.")
                return redirect(flag)
    target = request.GET.get("target", "").strip()
    return render(
        request,
        "flags/flag_detail.html",
        {
            "flag": flag,
            "form": form,
            "can_edit": can_edit,
            "history": flag.changes.select_related("actor"),
            "target": target,
            "target_result": flag.is_enabled_for(target) if target else None,
        },
    )


@require_POST
@permission_required("flags.change_featureflag", raise_exception=True)
def flag_toggle(request, pk):
    flag = get_object_or_404(FeatureFlag, pk=pk)
    form = CommentOnlyForm(request.POST)
    form.is_valid()
    try:
        flag = services.update_flag(
            flag,
            actor=request.user,
            enabled=not flag.enabled,
            comment=form.cleaned_data.get("comment", ""),
        )
    except ValidationError as exc:
        _form_errors(request, exc)
    else:
        messages.success(request, f"{flag.key} turned {'on' if flag.enabled else 'off'}.")
    return redirect(request.POST.get("next") or flag.get_absolute_url())


@require_POST
@permission_required("flags.change_featureflag", raise_exception=True)
def flag_archive(request, pk):
    flag = get_object_or_404(FeatureFlag, pk=pk)
    archived = request.POST.get("archived") == "1"
    services.set_archived(
        flag, archived=archived, actor=request.user, comment=request.POST.get("comment", "")
    )
    messages.success(request, f"{flag.key} {'archived' if archived else 'restored'}.")
    return redirect(flag)
