from django.db.models import Sum, F
from rest_framework import serializers, validators

from backend.models import Shop, Category, Product, User, Contact, ProductParameter, ProductInfo, Order, OrderItem


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name',  'url', 'address', 'state')

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'shop')

class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = ('id', 'name', 'category')

class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value')

class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'shop', 'model', 'product', 'description', 'quantity', 'price_rrc', 'product_parameters',)
        read_only_fields = ('id',)

class ContactSerializer(serializers.ModelSerializer):
    # Сюда потом можно добавить валидацию номера телефона, и номеров дома, кв и т.п.
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'write_only': True}
        }


class UserSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(read_only=True, many=True)

    class Meta:
        model = User
        fields = ('id', 'surname', 'first_name', 'last_name', 'email', 'company', 'position', 'contacts', 'is_active',)

        read_only_fields = ('id',)



class OrderItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderItem
        fields = ('id', 'quantity', 'product_info', 'order',)
        read_only_fields = ('id',)
        # extra_kwargs = {
        #     'order': {'write_only': True}
        # }

class ProductInfoShopSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'product', 'shop', 'model', 'description', 'product_parameters')


class OrderItemShopSerializer(OrderItemSerializer):
    product_info = ProductInfoShopSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'quantity', 'product_info', 'order',)
        read_only_fields = ('id',)


class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemShopSerializer(read_only=True, many=True)
    total_cost = serializers.IntegerField()    # при загрузке через annotate обязательно заявить тип данных
    class Meta:
        model = Order
        fields = ('id', 'status', 'date_time', 'ordered_items', 'contact', 'total_cost')
        read_only_fields = ('id',)


class OrderPartnerSerializer(serializers.ModelSerializer):
    product_info = ProductInfoShopSerializer(read_only=True)
    order_item_cost = serializers.IntegerField()
    contact = serializers.CharField(source='order.contact', allow_null=True)

    class Meta:
        model = OrderItem
        fields = ('order', 'product_info', 'quantity', 'order_item_cost', 'contact')
        read_only_fields = ('id',)