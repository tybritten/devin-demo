from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Min, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView

from . import services
from .forms import CommentForm, RefundFilterForm, RefundForm, TransitionForm
from .models import Refund

Status = Refund.Status
SCOPES = [
    ("pending", "Pending approval"),
    ("approved", "Awaiting payment"),
    ("mine", "My requests"),
    ("closed", "Closed"),
    ("all", "All"),
]
AGING_BUCKETS = [("0–2 days", 0, 2), ("3–7 days", 3, 7), ("8+ days", 8, None)]


def _actionable_for(user):
    """Refunds waiting on `user`: approvals they may give, and payments they may record."""
    approvals = Refund.objects.none()
    if user.has_perm("refunds.approve_refund"):
        approvals = Refund.objects.pending().exclude(requested_by=user)
        if not user.has_perm("refunds.approve_over_limit"):
            approvals = [r for r in approvals if not r.over_limit]
    payments = Refund.objects.none()
    if user.has_perm("refunds.mark_paid"):
        payments = Refund.objects.awaiting_payment()
    return approvals, payments


class DashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = "refunds.view_refund"
    template_name = "refunds/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        since = now - timedelta(days=30)
        refunds = Refund.objects.all()
        totals = refunds.aggregate(
            pending_count=Count("pk", filter=Q(status=Status.REQUESTED)),
            pending_total=Sum("amount", filter=Q(status=Status.REQUESTED)),
            oldest_pending=Min("created_at", filter=Q(status=Status.REQUESTED)),
            approved_count=Count("pk", filter=Q(status=Status.APPROVED)),
            approved_total=Sum("amount", filter=Q(status=Status.APPROVED)),
            paid_count=Count("pk", filter=Q(status=Status.PAID, paid_at__gte=since)),
            paid_total=Sum("amount", filter=Q(status=Status.PAID, paid_at__gte=since)),
            decided=Count("pk", filter=Q(decided_at__gte=since)),
            rejected=Count("pk", filter=Q(decided_at__gte=since, status=Status.REJECTED)),
        )
        totals["approval_rate"] = (
            round(100 * (totals["decided"] - totals["rejected"]) / totals["decided"])
            if totals["decided"]
            else None
        )
        by_reason = list(
            refunds.filter(created_at__gte=since)
            .values("reason")
            .annotate(count=Count("pk"), total=Sum("amount"))
            .order_by("-total")
        )
        top = max((r["total"] for r in by_reason), default=0) or 1
        labels = dict(Refund.Reason.choices)
        for row in by_reason:
            row["label"] = labels.get(row["reason"], row["reason"])
            row["pct"] = round(100 * row["total"] / top)
        aging = []
        for label, lo, hi in AGING_BUCKETS:
            qs = refunds.pending().filter(created_at__lte=now - timedelta(days=lo))
            if hi is not None:
                qs = qs.filter(created_at__gt=now - timedelta(days=hi + 1))
            aging.append((label, qs.count()))
        approvals, payments = _actionable_for(self.request.user)
        ctx.update(
            totals=totals,
            by_reason=by_reason,
            aging=aging,
            approvals=list(approvals)[:10],
            payments=list(payments[:10]),
            my_open=refunds.open().filter(requested_by=self.request.user)[:10],
        )
        return ctx


class RefundListView(PermissionRequiredMixin, ListView):
    permission_required = "refunds.view_refund"
    template_name = "refunds/refund_list.html"
    context_object_name = "refunds"
    paginate_by = 25

    def scoped(self, qs, scope):
        return {
            "pending": qs.pending(),
            "approved": qs.awaiting_payment(),
            "mine": qs.filter(requested_by=self.request.user),
            "closed": qs.closed(),
        }.get(scope, qs)

    def get_queryset(self):
        scope = self.request.GET.get("scope", "pending")
        self.scope = scope if scope in dict(SCOPES) else "pending"
        self.filter_form = RefundFilterForm(self.request.GET)
        qs = self.scoped(Refund.objects.select_related("requested_by"), self.scope)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data["reason"]:
                qs = qs.filter(reason=data["reason"])
            if q := data["q"].strip():
                search = (
                    Q(customer_name__icontains=q)
                    | Q(customer_ref__iexact=q)
                    | Q(order_ref__iexact=q)
                )
                ref = q.upper().removeprefix("RF-")
                if ref.isdigit():
                    search |= Q(pk=int(ref))
                qs = qs.filter(search)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(scope=self.scope, scopes=SCOPES, filter_form=self.filter_form)
        return ctx


class RefundDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "refunds.view_refund"
    model = Refund
    template_name = "refunds/refund_detail.html"
    context_object_name = "refund"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        refund, user = self.object, self.request.user
        statuses = services.allowed_transitions(refund, user)
        can_edit = refund.is_open and user.has_perm("refunds.change_refund")
        ctx.update(
            events=refund.events.select_related("actor"),
            can_edit=can_edit,
            transition_form=TransitionForm(statuses=statuses) if statuses and can_edit else None,
            comment_form=CommentForm(),
        )
        return ctx


@permission_required("refunds.add_refund", raise_exception=True)
def refund_create(request):
    form = RefundForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        refund = services.create_refund(actor=request.user, **form.cleaned_data)
        messages.success(request, f"Created {refund.reference}.")
        return redirect(refund)
    return render(request, "refunds/refund_form.html", {"form": form})


def _run_action(request, action):
    try:
        action()
    except (ValidationError, PermissionDenied) as exc:
        for msg in getattr(exc, "messages", None) or [str(exc)]:
            messages.error(request, msg)
        return False
    return True


@require_POST
@permission_required("refunds.change_refund", raise_exception=True)
def refund_transition(request, pk):
    refund = get_object_or_404(Refund, pk=pk)
    form = TransitionForm(request.POST, statuses=list(Status))
    if not form.is_valid():
        messages.error(request, "Choose a valid status.")
    elif _run_action(
        request,
        lambda: services.transition(
            refund,
            to_status=form.cleaned_data["to_status"],
            actor=request.user,
            comment=form.cleaned_data["comment"],
            payment_reference=form.cleaned_data["payment_reference"],
        ),
    ):
        refund.refresh_from_db()
        messages.success(request, f"{refund.reference} moved to {refund.get_status_display()}.")
    return redirect(refund)


@require_POST
@permission_required("refunds.change_refund", raise_exception=True)
def refund_comment(request, pk):
    refund = get_object_or_404(Refund, pk=pk)
    form = CommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Comment cannot be empty.")
    elif _run_action(
        request,
        lambda: services.add_comment(
            refund, actor=request.user, message=form.cleaned_data["message"]
        ),
    ):
        messages.success(request, "Comment added.")
    return redirect(refund)
