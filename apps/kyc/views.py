from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from . import services
from .forms import (
    AssignForm,
    CaseForm,
    CommentForm,
    CustomerForm,
    DocumentForm,
    QueueFilterForm,
    TransitionForm,
)
from .models import CaseDocument, Customer, ReviewCase

SCOPES = [
    ("mine", "Assigned to me"),
    ("unassigned", "Unassigned"),
    ("open", "All open"),
    ("closed", "Closed"),
]


class QueueView(PermissionRequiredMixin, ListView):
    permission_required = "kyc.view_reviewcase"
    template_name = "kyc/queue.html"
    context_object_name = "cases"
    paginate_by = 25

    def get_scope(self):
        scope = self.request.GET.get("scope", "mine")
        return scope if scope in dict(SCOPES) else "mine"

    def scoped(self, qs, scope):
        user = self.request.user
        if scope == "mine":
            return qs.open().filter(assigned_to=user)
        if scope == "unassigned":
            return qs.open().filter(assigned_to__isnull=True)
        if scope == "closed":
            return qs.closed()
        return qs.open()

    def get_queryset(self):
        self.scope = self.get_scope()
        self.filter_form = QueueFilterForm(self.request.GET)
        qs = self.scoped(ReviewCase.objects.select_related("customer", "assigned_to"), self.scope)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data["status"]:
                qs = qs.filter(status=data["status"])
            if data["risk"]:
                qs = qs.filter(risk_rating=data["risk"])
            if q := data["q"].strip():
                search = Q(customer__legal_name__icontains=q) | Q(customer__external_ref__iexact=q)
                ref = q.upper().removeprefix("KYC-")
                if ref.isdigit():
                    search |= Q(pk=int(ref))
                qs = qs.filter(search)
        if self.scope == "closed":
            return qs.order_by("-decided_at")
        return qs.order_by(F("due_date").asc(nulls_last=True), "created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        open_q = ~Q(status__in=ReviewCase.CLOSED_STATUSES)
        counts = ReviewCase.objects.aggregate(
            mine=Count("pk", filter=open_q & Q(assigned_to=user)),
            unassigned=Count("pk", filter=open_q & Q(assigned_to__isnull=True)),
            open=Count("pk", filter=open_q),
            closed=Count("pk", filter=~open_q),
        )
        ctx.update(
            scope=self.scope,
            scopes=[(key, label, counts[key]) for key, label in SCOPES],
            filter_form=self.filter_form,
        )
        return ctx


class CaseDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "kyc.view_reviewcase"
    model = ReviewCase
    template_name = "kyc/case_detail.html"
    context_object_name = "case"

    def get_queryset(self):
        return ReviewCase.objects.select_related(
            "customer", "assigned_to", "created_by", "decided_by"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case = self.object
        user = self.request.user
        statuses = services.allowed_transitions(case, user)
        ctx.update(
            events=case.events.select_related("actor"),
            documents=case.documents.select_related("uploaded_by"),
            other_cases=case.customer.cases.exclude(pk=case.pk).order_by("-created_at"),
            can_edit=case.is_open and user.has_perm("kyc.change_reviewcase"),
            assign_form=AssignForm(initial={"assignee": case.assigned_to}),
            transition_form=TransitionForm(statuses=statuses) if statuses else None,
            comment_form=CommentForm(),
            document_form=DocumentForm(),
        )
        return ctx


@permission_required("kyc.add_reviewcase", raise_exception=True)
def case_create(request):
    if request.method == "POST":
        existing = None
        if ref := request.POST.get("external_ref", "").strip():
            existing = Customer.objects.filter(external_ref=ref).first()
        customer_form = CustomerForm(request.POST)
        case_form = CaseForm(request.POST)
        # An existing customer is linked as-is; intake never edits customer records.
        customer_ok = existing is not None or customer_form.is_valid()
        if customer_ok and case_form.is_valid():
            with transaction.atomic():
                customer = existing or customer_form.save()
                case = services.create_case(
                    customer=customer, actor=request.user, **case_form.cleaned_data
                )
            if existing:
                messages.info(
                    request, f"Linked to existing customer {customer}; their details are unchanged."
                )
            messages.success(request, f"Created {case.reference}.")
            return redirect(case)
    else:
        customer_form = CustomerForm()
        case_form = CaseForm()
    return render(
        request, "kyc/case_form.html", {"customer_form": customer_form, "case_form": case_form}
    )


def _run_action(request, action):
    try:
        action()
    except (ValidationError, PermissionDenied) as exc:
        for msg in getattr(exc, "messages", None) or [str(exc)]:
            messages.error(request, msg)
        return False
    return True


@require_POST
@permission_required("kyc.change_reviewcase", raise_exception=True)
def case_claim(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    if _run_action(
        request, lambda: services.assign(case, assignee=request.user, actor=request.user)
    ):
        messages.success(request, f"{case.reference} assigned to you.")
    return redirect(case)


@require_POST
@permission_required("kyc.change_reviewcase", raise_exception=True)
def case_assign(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    form = AssignForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a valid assignee.")
    elif _run_action(
        request,
        lambda: services.assign(case, assignee=form.cleaned_data["assignee"], actor=request.user),
    ):
        messages.success(request, "Assignment updated.")
    return redirect(case)


@require_POST
@permission_required("kyc.change_reviewcase", raise_exception=True)
def case_transition(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    form = TransitionForm(request.POST, statuses=ReviewCase.Status)
    if not form.is_valid():
        messages.error(request, "Choose a valid status.")
    elif _run_action(
        request,
        lambda: services.transition(
            case,
            to_status=form.cleaned_data["to_status"],
            actor=request.user,
            comment=form.cleaned_data["comment"],
        ),
    ):
        case.refresh_from_db()
        messages.success(request, f"{case.reference} moved to {case.get_status_display()}.")
    return redirect(case)


@require_POST
@permission_required("kyc.change_reviewcase", raise_exception=True)
def case_comment(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    form = CommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Comment cannot be empty.")
    elif _run_action(
        request,
        lambda: services.add_comment(
            case, actor=request.user, message=form.cleaned_data["message"]
        ),
    ):
        messages.success(request, "Comment added.")
    return redirect(case)


@require_POST
@permission_required(
    ["kyc.view_reviewcase", "kyc.change_reviewcase", "kyc.add_casedocument"],
    raise_exception=True,
)
def document_upload(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    form = DocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    elif _run_action(
        request,
        lambda: services.add_document(
            case,
            actor=request.user,
            document_type=form.cleaned_data["document_type"],
            file=form.cleaned_data["file"],
        ),
    ):
        messages.success(request, "Document uploaded.")
    return redirect(case)


@permission_required(["kyc.view_reviewcase", "kyc.view_casedocument"], raise_exception=True)
def document_download(request, pk):
    doc = get_object_or_404(CaseDocument, pk=pk)
    return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.original_name)
