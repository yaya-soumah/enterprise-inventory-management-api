from rest_framework import viewsets, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.http import HttpResponse
from django.db.models import Sum, F
from django.db import transaction
import csv
from .models import Warehouse, Product, Stock, Order, OrderItem
from .serializers import WarehouseSerializer, ProductSerializer, StockSerializer, OrderSerializer
from .tasks import send_low_stock_alert

class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['name', 'location']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Warehouse.objects.all()
        return Warehouse.objects.filter(manager=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            serializer.save()
        else:
            serializer.save(manager=self.request.user)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['name', 'sku']

class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['warehouse', 'product']

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        threshold = int(request.query_params.get('threshold', 10))
        low_stock = Stock.objects.filter(quantity__lte=threshold)
        serializer = StockSerializer(low_stock, many=True)
        if low_stock.exists():
            send_low_stock_alert.delay(threshold)
        return Response(serializer.data)

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'warehouse']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        with transaction.atomic():
            validated_data = serializer.validated_data
            items_data = validated_data.pop('items', [])
            warehouse = validated_data.get('warehouse')
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                try:
                    stock = Stock.objects.select_for_update().get(warehouse=warehouse, product=product)
                    if stock.quantity < quantity:
                        raise serializers.ValidationError(
                            f'Insufficient stock for {product.name}: {stock.quantity} available, {quantity} requested.'
                        )
                except Stock.DoesNotExist:
                    raise serializers.ValidationError(
                        f'No stock available for {product.name} in warehouse {warehouse.name}.'
                    )

            order = serializer.save(user=self.request.user)
            for item_data in items_data:
                OrderItem.objects.create(order=order, **item_data)
                Stock.objects.filter(warehouse=warehouse, product=item_data['product']).update(
                    quantity=F('quantity') - item_data['quantity']
                )
    def perform_update(self, serializer):
        with transaction.atomic():
            order = serializer.instance
            if serializer.validated_data.get('status') == 'FULFILLED' and order.status != 'FULFILLED':
                if not order.warehouse:
                    raise serializers.ValidationError('Warehouse is required for fulfilled orders.')
                for item in order.items.all():
                    stock = Stock.objects.select_for_update().get(warehouse=order.warehouse, product=item.product)
                    if stock.quantity < item.quantity:
                        raise serializers.ValidationError(f'Insufficient stock for {item.product.name}.')
                    stock.quantity -= item.quantity
                    stock.save()
                    item.fulfilled_quantity = item.quantity
                    item.save()
                serializer.save()

    @action(detail=False, methods=['get'])
    def export_orders(self, request):
        queryset = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'User', 'Warehouse', 'Status', 'Created At', 'Total Items'])
        for order in queryset:
            total_items = order.items.aggregate(Sum('quantity'))['quantity__sum'] or 0
            warehouse_name = order.warehouse.name if order.warehouse else ''
            writer.writerow([order.id, order.user.username, warehouse_name, order.status, order.created_at, total_items])
        return response
