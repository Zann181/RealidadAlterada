from datetime import datetime, timedelta

from django.utils import timezone


def apply_period_filter(request, queryset, date_field):
    period = (request.GET.get("period") or "").strip()
    fecha_str = (request.GET.get("fecha") or "").strip()
    selected_date = timezone.localdate()

    if fecha_str:
        try:
            selected_date = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()

    if period == "dia":
        queryset = queryset.filter(**{f"{date_field}__date": selected_date})
    elif period == "semana":
        start_date = selected_date - timedelta(days=selected_date.weekday())
        end_date = start_date + timedelta(days=7)
        queryset = queryset.filter(
            **{
                f"{date_field}__date__gte": start_date,
                f"{date_field}__date__lt": end_date,
            }
        )
    elif period == "mes":
        queryset = queryset.filter(
            **{
                f"{date_field}__year": selected_date.year,
                f"{date_field}__month": selected_date.month,
            }
        )
    elif period == "anio":
        queryset = queryset.filter(**{f"{date_field}__year": selected_date.year})

    return queryset, period, selected_date
