from django.db import models
from django.contrib.auth.models import User

class Warehouse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL,null=True,blank=True, related_name='managed_warehouses')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

class Stock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    quantity = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'product')

    def __str__(self):
        return f'{self.product.name} @ {self.warehouse.name}'

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('FULFILLED', 'Fulfilled'),
        ('CANCELLED', 'Cancelled'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL,null=True,blank=True, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.id} - {self.status}'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    fulfilled_quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

