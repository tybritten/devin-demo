from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from . import services
from .forms import CommentForm, FilterForm, TransitionForm, __Model__Form
from .models import __Model__

VIEW_PERM = "__app__.view___model__"


def _transition_choices(record, user):
    return [(s.value, s.label) for s in services.allowed_transitions(record, user)]


class RecordListView(PermissionRequiredMixin, ListView):
    permission_required = VIEW_PERM
    template_name = "__app__/list.html"
    context_object_name = "records"
    paginate_by = 25

    def get_queryset(self):
        qs = __Model__.objects.select_related("owner")
        self.filter_form = FilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            if q := self.filter_form.cleaned_data["q"]:
                qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
            if status := self.filter_form.cleaned_data["status"]:
                qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        return super().get_context_data(filter_form=self.filter_form, **kwargs)


class RecordDetailView(PermissionRequiredMixin, DetailView):
    permission_required = VIEW_PERM
    model = __Model__
    template_name = "__app__/detail.html"
    context_object_name = "record"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        record, user = self.object, self.request.user
        choices = _transition_choices(record, user)
        ctx.update(
            events=record.events.select_related("actor"),
            can_edit=services.can_edit(record, user),
            transition_form=TransitionForm(choices=choices) if choices else None,
            comment_form=CommentForm(),
        )
        return ctx


@permission_required(services.ADD_PERM, raise_exception=True)
def record_create(request):
    form = __Model__Form(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = services.create_record(actor=request.user, **form.cleaned_data)
        messages.success(request, f"Created “{record}”.")
        return redirect(record)
    return render(request, "__app__/form.html", {"form": form})


@permission_required(services.CHANGE_PERM, raise_exception=True)
def record_edit(request, pk):
    record = get_object_or_404(__Model__, pk=pk)
    if not services.can_edit(record, request.user):
        raise PermissionDenied
    form = __Model__Form(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        services.update_record(record, actor=request.user, **form.cleaned_data)
        messages.success(request, "Saved.")
        return redirect(record)
    return render(request, "__app__/form.html", {"form": form, "record": record})


@require_POST
@permission_required(services.CHANGE_PERM, raise_exception=True)
def record_transition(request, pk):
    record = get_object_or_404(__Model__, pk=pk)
    form = TransitionForm(request.POST, choices=_transition_choices(record, request.user))
    if not form.is_valid():
        messages.error(request, "That status change isn't allowed.")
        return redirect(record)
    try:
        services.transition(
            record,
            to_status=form.cleaned_data["to_status"],
            actor=request.user,
            comment=form.cleaned_data["comment"],
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Status updated.")
    return redirect(record)


@require_POST
@permission_required(services.CHANGE_PERM, raise_exception=True)
def record_comment(request, pk):
    record = get_object_or_404(__Model__, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        services.add_comment(record, actor=request.user, message=form.cleaned_data["message"])
    return redirect(record)
