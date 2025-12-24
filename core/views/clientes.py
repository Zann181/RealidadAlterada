from django.shortcuts import render

from core.views.permissions import client_required


@client_required
def cliente_dashboard(request):
    context = {}
    return render(request, "core/clientes/dashboard.html", context)
