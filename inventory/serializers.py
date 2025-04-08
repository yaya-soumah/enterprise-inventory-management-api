from rest_framework import serializers
from inventory.models import Warehouse, Stock, Product, Order, OrderItem

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['id', 'warehouse', 'quantity', 'product', 'last_updated']
        read_only_fields = ['last_updated']

class WarehouseSerializer(serializers.ModelSerializer):
    stocks = StockSerializer(many=True, read_only=True)
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location', 'manager', 'stocks']
        read_only_fields = ['manager']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'sku']

    def validate_sku(self, value):
        if not value.isalnum():  # Should be value.isalnum()
            raise serializers.ValidationError('SKU must be alphanumeric.')
        return value

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'fulfilled_quantity']
        read_only_fields = ['fulfilled_quantity']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive.')
        return value

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = Order
        fields = ['id', 'user', 'warehouse', 'status', 'created_at', 'items']
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def validate(self, data):
        if data.get('status') == 'FULFILLED' and not data.get('warehouse'):
            raise serializers.ValidationError('Warehouse is required for fulfilled orders')
        if not data.get('warehouse') and data.get('items', []):
            raise serializers.ValidationError('Warehouse is required when items are specified.')
        return data