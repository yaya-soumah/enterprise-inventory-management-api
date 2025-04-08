import jwt
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from .models import Warehouse, Product, Stock, Order, OrderItem


class InventoryAPITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.admin = User.objects.create_superuser(username='admin', password='adminpass')

        cls.warehouse = Warehouse.objects.create(name='WH1', location='Shanghai', manager=cls.user)
        cls.product = Product.objects.create(name='Laptop', sku='LT123', description='High-end laptop')
        cls.product2 = Product.objects.create(name='Phone2', sku='PH2123', description='Smartphone')
        cls.stock = Stock.objects.create(warehouse=cls.warehouse, product=cls.product, quantity=50)
        cls.stock2 = Stock.objects.create(warehouse=cls.warehouse, product=cls.product2, quantity=0)
        cls.order = Order.objects.create(user=cls.user, warehouse=cls.warehouse, status='PENDING')
        OrderItem.objects.create(order=cls.order, product=cls.product, quantity=5)

    def setUp(self):
        self.client = APIClient()
        response = self.client.post('/api/token/', {'username': 'testuser', 'password': 'testpass'}, format='json')
        self.token = response.data['access']
        decoded = jwt.decode(self.token, options={'verify_signature': False}, )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        response = self.client.post('/api/token/', {'username': 'admin', 'password': 'adminpass'}, format='json')
        self.admin_token = response.data['access']

    def test_create_product(self):
        data = {'name': 'Phone', 'sku': 'PH123', 'description': 'Smartphone'}
        response = self.client.post('/api/products/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(response.data['sku'], 'PH123')

    def test_list_products(self):  # Fixed name
        response = self.client.get('/api/products/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_create_warehouse_as_user(self):
        data = {'name': 'WH2', 'location': 'Beijing'}
        response = self.client.post('/api/warehouses/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Warehouse.objects.get(name='WH2').manager, self.user)

    def test_admin_sees_all_warehouses(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.admin_token)
        Warehouse.objects.create(name='WH3', location='Guangzhou')
        response = self.client.get('/api/warehouses/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_user_sees_only_managed_warehouses(self):
        Warehouse.objects.create(name='WH3', location='Guangzhou')
        response = self.client.get('/api/warehouses/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_update_stock(self):
        data = {'quantity': 75}
        response = self.client.patch(f'/api/stocks/{self.stock.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 75)

    def test_low_stock_action(self):
        Stock.objects.create(warehouse=self.warehouse, product=Product.objects.create(name='Phone', sku='PH12'), quantity=5)
        response = self.client.get('/api/stocks/low_stock/?threshold=10', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['quantity'], 0)

    def test_create_order_with_items(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': 3}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(OrderItem.objects.filter(order__id=response.data['id']).count(), 1)

    def test_export_orders(self):
        response = self.client.get('/api/orders/export_orders/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('ID,User,Warehouse,Status,Created At,Total Items', content)
        self.assertIn(f'{self.order.id},testuser,WH1,PENDING', content)

    def test_order_fulfilled_validation(self):
        data = {'status': 'FULFILLED', 'items': [{'product': self.product.id, 'quantity': 2}]}
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Warehouse is required for fulfilled orders', str(response.data['non_field_errors']))

    def test_create_order(self):
        order_data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': 5}]
        }
        response = self.client.post('/api/orders/', order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_sku_rejected(self):
        data = {'name': 'Laptop Duplicate', 'sku': 'LT123', 'description': 'Duplicate SKU'}
        response = self.client.post('/api/products/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sku', response.data)

    def test_negative_quantity_rejected(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': -1}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data['items'][0])

    def test_invalid_status_rejected(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'INVALID',
            'items': [{'product': self.product.id, 'quantity': 2}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)

    def test_unauthorized_access(self):
        self.client.credentials()
        response = self.client.get('/api/products/', format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pagination_with_multiple_products(self):
        for i in range(25):
            Product.objects.create(name=f'Product {i}', sku=f'SKU{i:03d}', description='Test')
        response = self.client.get('/api/products/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])

    def test_stock_limit_on_order_insufficient(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': 60}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(response.data))

    def test_stock_reduction_on_order_success(self):
        initial_quantity = self.stock.quantity
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': 10}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, initial_quantity - 10)

    def test_order_without_warehouse_with_items(self):
        data = {
            'status': 'PENDING',
            'items': [{'product': self.product.id, 'quantity': 5}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Warehouse is required when items are specified', str(response.data['non_field_errors']))

    def test_zero_stock_rejected(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [{'product': self.product2.id, 'quantity': 1}]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(response.data))

    def test_multiple_items_mixed_stock(self):
        data = {
            'warehouse': self.warehouse.id,
            'status': 'PENDING',
            'items': [
                {'product': self.product.id, 'quantity': 10},
                {'product': self.product2.id, 'quantity': 5}
            ]
        }
        response = self.client.post('/api/orders/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(response.data))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 50)

    def test_max_field_length(self):
        long_name = 'W' * 101
        data = {'name': long_name, 'location': 'Beijing'}
        response = self.client.post('/api/warehouses/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_null_required_field(self):
        data = {'location': 'Beijing'}
        response = self.client.post('/api/warehouses/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_single_order(self):
        token = self.token

        def create_order(data):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            return client.post('/api/orders/', data, format='json')

        data = {'warehouse': self.warehouse.id, 'status': 'PENDING',
                'items': [{'product': self.product.id, 'quantity': 40}]}
        response = create_order(data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
