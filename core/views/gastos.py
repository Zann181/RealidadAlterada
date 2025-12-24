from django.contrib import messages
from django.shortcuts import render, redirect

from core.forms.gastos import CategoriaGastoForm, GastoForm
from core.models import Gasto
from core.views.filters import apply_period_filter
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required


@panel_required
def gasto_list(request):
    gastos = Gasto.objects.select_related("categoria_gasto")
    gastos, period, selected_date = apply_period_filter(request, gastos, "fecha")
    gastos = gastos.order_by("-fecha")
    pagination = paginate_queryset(request, gastos)
    form_type = request.POST.get("form_type")
    form = GastoForm()
    categoria_form = CategoriaGastoForm()

    if request.method == "POST" and form_type == "gasto":
        form = GastoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto registrado.")
            return redirect("core:gastos_list")
    elif request.method == "POST" and form_type == "categoria_gasto":
        categoria_form = CategoriaGastoForm(request.POST)
        if categoria_form.is_valid():
            categoria_form.save()
            messages.success(request, "Categoria de gasto creada.")
            return redirect("core:gastos_list")

    return render(
        request,
        "core/gastos/gastos_list.html",
        {
            "gastos": pagination["page_obj"],
            "form": form,
            "categoria_form": categoria_form,
            "period": period,
            "fecha": selected_date.strftime("%Y-%m-%d"),
            **pagination,
        },
    )
