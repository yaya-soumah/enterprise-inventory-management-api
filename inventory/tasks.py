from celery import shared_task
from django.core.mail import send_mail
from .models import Stock

@shared_task
def send_low_stock_alert(threshold):
    low_stock =  Stock.objects.filter(quantity__lte=threshold)
    if low_stock.exists():
        message = "Low stock alert:\n" + "\n".join([f'{s.product.name} @ {s.warehouse.name}: {s.quantity}' for s in low_stock])
        send_mail(
            'Low Stock Alert',
            message,
            'from@example.com',
            ['admin@example.com'],
            fail_silently=False,
        )