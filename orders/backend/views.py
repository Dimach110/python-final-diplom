from pprint import pprint

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError

from django.http import JsonResponse
from requests import get
from django.http import HttpRequest, JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import load as load_yaml, Loader
from ujson import loads as load_json
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, F
from backend.decorators import query_debugger

from backend.models import Shop, ProductInfo, Product, Parameter, ProductParameter, Category, Order, OrderItem, Contact
from backend.serializers import ProductSerializer, ShopSerializer, UserSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, OrderPartnerSerializer, ContactSerializer, CategorySerializer
from backend.models import ConfirmEmailToken
from backend.signals import new_user_registered, new_order


class ShopView(APIView):

    def get(self, request, *args, **kwargs):
        """Просмотр всех магазинов"""
        queryset = Shop.objects.all()
        serializer = ShopSerializer(queryset, many=True)
        return Response(serializer.data)

    # def post(self, request, *args, **kwargs):
    #     """Добавление нового магазина"""
    #     data = request.data
    #     serializer = ShopSerializer(data=data)
    #     try:
    #         res = Shop.objects.get(name=data['name'])
    #     except:
    #         res = None
    #     if res == None:
    #         if serializer.is_valid():
    #             serializer.save()
    #             return JsonResponse(serializer.data)
    #         elif not serializer.is_valid():
    #             return Response(serializer.errors)
    #     else:
    #         return Response(f"Ошибка. Такой магазин уже существует с id {res.id} , укажите другое название")

class CategoryView(ListAPIView):
    """ Класс для просмотра категорий """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductView(APIView):
    """ Класс для просмотра товаров """
    @query_debugger
    def get(self, request, *args, **kwargs):
        # Присваиваем переменным параметры
        product_id = request.GET.get('product_id')
        shop_id = request.GET.get('shop_id')
        category_id = request.GET.get('category_id')
        query_st = Q(shop__state=True)

        # Поиск по категории везде или с учётом магазина
        if category_id:  # Если параметр не None
            query = query_st & Q(product__category_id=category_id)
            if shop_id:
                query = query & Q(shop_id=shop_id)

        # Поиск по магазину всех товаров или с учётом конкретного товара
        elif shop_id:
            query = query_st & Q(shop_id=shop_id)
            if product_id:
                query = query & Q(product_id=product_id)

        # Поиск везде конкретного товара
        elif product_id:
            query = query_st & Q(product_id=product_id)

        # Выгрузка списка всех товаров
        else:
            queryset = ProductInfo.objects.all().select_related().prefetch_related(
                'product_parameters__parameter')
            serializer = ProductInfoSerializer(queryset, many=True)
            return Response(serializer.data)

        queryset = ProductInfo.objects.filter(query). \
            select_related('shop', 'product__category').prefetch_related(
            'product_parameters__parameter')
        # select_related позволяет осуществить только один запрос (сокращает время)
        # Обеспечивает пересылку ForeignKey, OneToOne и обратный OneToOne.
        # Для обработки связи ManyToMany и обратных ManyToMany, ForeignKey использовать prefetch_related
        # для устранения дубликатов можно применить .distinct() например по модели .distinct('model')
        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление новых продуктов"""
        if not request.user.is_authenticated:
            return JsonResponse({'Status': '403',
                                 'Error': 'Ошибка аутентификации пользователя'},
                                status=403)
        if request.user.type != 'seller':
            return JsonResponse({'Status': '403',
                                 'Error': 'Загрузку может осуществлять только продавец'},
                                status=403)
        data = request.data
        serializer = ProductSerializer(data=data)
        try:
            res = Product.objects.get(name=data['name'])
        except:
            res = None
        if res == None:
            if serializer.is_valid():
                serializer.save()
                return JsonResponse(serializer.data)
            elif not serializer.is_valid():
                return Response(serializer.errors)
        else:
            return JsonResponse({'Status': '405',
                                 'Error': f'Ошибка. Такой продукт уже существует с id {res.id} укажите другое название'},
                                status=405)

class ImportPrice(APIView):
    # pass
    """Загрузка (импорт) списка продуктов"""

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': '403',
                                 'Error': 'Ошибка аутентификации пользователя'},
                                status=403)
        if request.user.type != 'seller':
            return JsonResponse({'Status': '403',
                                 'Error': 'Загрузку может осуществлять только продавец'},
                                status=403)

        url = request.data.get('url')

        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as error:
                return JsonResponse({'Status': False, 'Error': str(error)})
            else:
                stream = get(url).content  # забираем данные в формате bytes
                data = load_yaml(stream, Loader=Loader)  # загружаем через yaml и получаем данные в формате dict

                # далее распарсим данные из словаря и загружаем из в базу
                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
                for category in data['categories']:
                    # добавляем если ещё не существуют категории
                    category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                    category_object.shops.add(shop.id)  # отдельно добавляем id магазина
                    category_object.save()
                # отчищаем старые данные о товарах по этому магазину
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
                    # Так как данные старые мы удалили, создаём заново из нашего нового прайса
                    product_info = ProductInfo.objects.create(product_id=product.id,
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              quantity=item['quantity'],
                                                              shop_id=shop.id)
                    for name, value in item['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(product_info_id=product_info.id,
                                                        parameter_id=parameter_object.id,
                                                        value=value)

                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указана ссылка на прайс-лист'})


class LoginUser(APIView):
    """Вход пользователей. Аутентификация."""

    def post(self, request, *args, **kwargs):
        # проверяем что данные email и пароля присутствуют в запросе
        if {'login', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['login'], password=request.data['password'])
            # Проверяем на соответствие email - password
            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({"Status": True, "Token": token.key})
                else:
                    JsonResponse({"Status": False, "Errors": "Пользователь заблокирован, обратитесь к Администратору"})
            else:
                return JsonResponse({"Status": False, "Errors": 'Не правильно введён логин или пароль'})
        else:
            return JsonResponse({"Status": False,
                                 "Errors": "Не указаны необходимые аргументы ('email:' и 'password:')"})


class RegisterUser(APIView):
    """Регистрация новых пользователей"""

    def post(self, request, *args, **kwargs):
        # проверяем что введены все необходимые данные (email, pass)
        if {'surname', 'first_name', 'last_name', 'email', 'password1', 'password2'}.issubset(request.data):
            if request.data['password1'] == request.data['password2']:
                # Проводим проверку на сложность пароля
                try:
                    validate_password(request.data['password1'])
                except Exception as password_error:
                    # Exception имеет тип class 'django.core.exceptions.ValidationError',
                    # и для его вывода в Response его надо разобрать циклом и каждый элемент добавить в список
                    error_list = []
                    for error in password_error:
                        error_list.append(error)
                    return JsonResponse({'Status': False, 'Errors': {'password': error_list}})
                request.data.update({})
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():  # Если прошла проверка сериалайзером, то сохраняем
                    # Добавил is_active=True для отладки без почты (конфликт с почтовым сервисом)
                    user = user_serializer.save(is_active=True)
                    # user = user_serializer.save()
                    user.set_password(request.data['password1'])
                    user.save()
                    # Далее посылаем сигнал используя модуль почтовика
                    # Отключил для отладки без почты (конфликт с почтовым сервисом)
                    # new_user_registered.send(sender=self.__class__, user_id=user.id)
                    return JsonResponse({'Status': True, "Message": "Регистрация прошла успешно"})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})
            else:
                return JsonResponse({'Status': False, 'Error': 'Пароли не совпадают'})
        else:
            return JsonResponse({"Status": False, "Error": "Не введены все требуемые для регистрации данные"})



class RegisterPartner(APIView):
    """Регистрация новых партнёров"""

    def post(self, request, *args, **kwargs):
        if {'surname', 'first_name', 'last_name', 'email', 'password1', 'password2', 'company', 'position'}.issubset(
                request.data):
            if request.data['password1'] == request.data['password2']:
                try:
                    validate_password(request.data['password1'])
                except Exception as password_error:
                    print(type(password_error))
                    error_list = []
                    for error in password_error:
                        error_list.append(error)
                    return JsonResponse({'Status': False, 'Errors': {'password': error_list}})
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # Добавил is_active=True для отладки без почты (конфликт с почтовым сервисом)
                    user = user_serializer.save(is_active=True, type='seller')
                    # user = user_serializer.save(type='seller')
                    user.set_password(request.data['password1'])
                    user.save()
                    # Далее посылаем сигнал используя модуль почтовика
                    # Отключил для отладки без почты (конфликт с почтовым сервисом)
                    # new_user_registered.send(sender=self.__class__, user_id=user.id)

                    return JsonResponse({'Status': True, "Message": "Регистрация прошла успешно"})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})
            else:
                return JsonResponse({'Status': False, 'Error': 'Пароли не совпадают'})
        else:
            return JsonResponse({"Status": False, "Error": "Не введены все требуемые для регистрации данные"})


class ConfirmAccount(APIView):
    """ Класс для подтверждения почтового адреса и активации УЗ """
    # Регистрация методом POST
    def post(self, request, *args, **kwargs):

        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})



class Basket(APIView):
    @query_debugger
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)

        basket = Order.objects.filter(
            user_id=request.user.id, status='basket').prefetch_related(
            'ordered_items__product_info__product', 'ordered_items__product_info__shop',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_cost=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(selfself, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)

        items = request.data.get('items')

        if type(items) == list:
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, status='basket')
            # в переменную _ записывается параметр сигнализирующий было ли создание,
            # True - Создалась запись в БД, False - запись существует

            # Проработка модуля на проверку наличие в заказе product_info с таким ID
            ordered_items = OrderItem.objects.filter(order=basket.id)
            existing_objects = OrderItemSerializer(ordered_items, many=True)
            created_index = 0
            update_index = 0
            for item in items:
                if {'product_info', 'quantity'}.issubset(item):
                    # добавляем ключ (order) и ID заказа (order.id) в словарь
                    item.update({'order': basket.id})
                    update_object = False
                    for order_item in existing_objects.data:
                        if order_item['product_info'] == item['product_info']:
                            OrderItem.objects.filter(product_info=item['product_info']). \
                                update(quantity=item['quantity'] + order_item['quantity'])
                            update_object = True


                    serializer = OrderItemSerializer(data=item)
                    if serializer.is_valid() and update_object is not True:
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            created_index += 1
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})
                else:
                    return JsonResponse({'Status': False,
                                         'Errors': "Не указаны все необходимые аргументы "
                                                   "Пример:('product_info': value, 'quantity': value)"
                                         })
            return JsonResponse({'Status': True, 'Message': f'В корзину добавлено товаров {created_index}, '
                                                            f'обновлено {update_index}'})
        else:
            return JsonResponse({'Status': False, 'Errors': 'Аргументы необходимо передавать в значении ключа "items" '
                                                            'в виде списка'})

    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        items = request.data['items']
        if type(items) == list:
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, status='basket')
            objects_updated = 0
            for item in items:

                if type(item['id']) == int and type(item['quantity']) == int:
                    objects_updated += OrderItem.objects.filter(id=item['id']).update(quantity=item['quantity'])
                    return JsonResponse({'Status': True, 'Message': f'Обновлено позиций: {objects_updated}'})
                    # тут не совсем честный отчёт по количеству обновлённых позиций,
                    # запрос update выдаёт в ответ на запрос кол-во найденных элементов,
                    # не учитывая совпало текущее значение переданное в update() с новым значением
                else:
                    return JsonResponse({'Status': False,
                                         'Errors': 'Должны быть переданы аргументы номера позиции (id)'
                                                   'и количества единиц товара (quantity) обязательно типа int'})
        else:
            return JsonResponse({'Status': False, 'Errors': 'Аргументы необходимо передавать в значении ключа "items" '
                                                            'в виде списка'})

    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        items = request.data['items']
        if type(items) == list:
            basket, _ = Order.objects.get_or_create(user_id=request.user.id,
                                                    status='basket')
            deleted_items = 0
            for item_id in items:
                if type(item_id) != int:  # проверяем что аргумент типа int
                    return JsonResponse({'Status': False,
                                         'Errors': 'ID удаляемого объекта должен передаваться типа int'})
                # Индекс [0] позволяет присвоить переменной deleted_items кол-во удалённых объектов
                deleted_items += OrderItem.objects.filter(order_id=basket.id, id=item_id).delete()[0]
                print(deleted_items)
            return JsonResponse({'Status': True, 'Message': f'Из корзины удалено товаров {deleted_items}'})



        else:
            return JsonResponse({'Status': False, 'Errors': 'Удаляемые объекты необходимо передавать,'
                                                            ' как значение ключа items в виде списке'})


class ContactView(APIView):
    """Класс работы пользователей с контактами"""

    @query_debugger
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        contact = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        contact = request.data

        if {'city', 'street', 'house', 'structure', 'building', 'apartment', 'phone'}.issubset(contact):
            contact._mutable = True    # делаем объект изменяемым
            contact.update({'user': request.user.id})
            serializer = ContactSerializer(data=contact)
            if serializer.is_valid():
                try:
                    serializer.save()
                except IntegrityError as error:
                    return JsonResponse({'Status': False, 'Errors': str(error)})
                else:
                    return JsonResponse({'Status': True, 'Message': 'Контакты добавлены успешно'})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})
        else:
            return JsonResponse({'Status': False, 'Errors': "Не указанны необходимые параметры:"
                                                            "'city', 'street', 'house', 'structure', 'building', "
                                                            "'apartment', 'phone'"})

    def put(self, request, contact_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)

        contact = Contact.objects.get(id=contact_id, user_id=request.user.id)
        print(request.data)
        if contact:
            serializer = ContactSerializer(instance=contact, data=request.data, partial=True)
            # partial=True позволяет передавать на изменения не все параметры, а только выборочные (частично)
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True, 'Message': 'Данные контакта обновлены'})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})
        else:
            return JsonResponse({'Status': False, 'Message': 'Контакт не найден'})

    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)

        items = request.data['items']
        if type(items) == list:
            deleted_items = 0
            for item_id in items:
                if type(item_id) != int:  # проверяем что аргумент типа int
                    return JsonResponse({'Status': False,
                                         'Errors': 'ID удаляемого объекта должен передаваться типа int'})
                # Индекс [0] позволяет присвоить переменной deleted_items кол-во удалённых объектов
                deleted_items += Contact.objects.filter(id=item_id, user_id=request.user.id).delete()[0]
                print(deleted_items)
            return JsonResponse({'Status': True, 'Message': f'Удалено контактов {deleted_items}'})
        else:
            return JsonResponse({'Status': False, 'Message': 'Контакт не найден'})


class PartnerOrder(APIView):
    """Класс для запроса поставщиком всех товаров с номерами заказов"""

    @query_debugger
    def get(self, request, order_id=None, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        if request.user.type != 'seller':
            return JsonResponse({'Status': False,
                                 'Error': 'Ошибка аутентификации - доступ разрешён только партнёрам'}, status=403)

        if order_id:
            order_item = OrderItem.objects.filter(product_info__shop__user_id=request.user.id, order__id=order_id) \
                .exclude(order__status='basket').prefetch_related(
                'product_info__product_parameters__parameter', 'product_info__shop',
                'product_info__product', ).select_related('order__contact') \
                .annotate(order_item_cost=F('quantity') * F('product_info__price_rrc')).distinct()

        else:
            order_item = OrderItem.objects.filter(product_info__shop__user_id=request.user.id) \
                .exclude(order__status='basket').prefetch_related(
                'product_info__product_parameters__parameter', 'product_info__shop',
                'product_info__product', ).select_related('order__contact') \
                .annotate(order_item_cost=F('quantity') * F('product_info__price_rrc')).distinct()

        if order_item:
            serializer = OrderPartnerSerializer(order_item, many=True)
            total_sum = 0
            for data in serializer.data:
                total_sum += data['order_item_cost']
            return JsonResponse({'orders': serializer.data, 'total_sum': total_sum})
        else:
            return Response('Заказов по магазину нет')


class OrderView(APIView):
    """
    Класс для получения и размещения заказов пользователями
    """

    @query_debugger
    def get(self, request, order_id=None, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)
        if order_id:
            order = Order.objects.filter(user__id=request.user.id, id=order_id). \
                exclude(status='basket').select_related('contact', ).prefetch_related(
                'ordered_items__product_info', 'ordered_items__product_info__product',
                'ordered_items__product_info__shop', 'ordered_items__product_info__product_parameters__parameter'
            ).annotate(total_cost=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price_rrc'))) \
                .distinct()
        else:
            order = Order.objects.filter(user__id=request.user.id). \
                exclude(status='basket').select_related('contact').prefetch_related(
                'ordered_items__product_info', 'ordered_items__product_info__product',
                'ordered_items__product_info__shop', 'ordered_items__product_info__product_parameters__parameter'
            ).annotate(total_cost=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price_rrc'))) \
                .distinct()
        if order:
            serializer = OrderSerializer(order, many=True)
            return JsonResponse({'Orders': serializer.data})
        else:
            return Response('У вас нет оформленных Заказов')

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Ошибка аутентификации'}, status=403)

        if {'order_id', 'contact_id'}.issubset(request.data):
            contact_id = request.data['contact_id']
            order_id = request.data['order_id']
            print(order_id, contact_id)
            if order_id.isdigit() and contact_id.isdigit():
                try:
                    order = Order.objects.filter(user_id=request.user.id, id=order_id, status='basket').update(
                            status='new', contact_id=contact_id)
                except IntegrityError as error:
                    return JsonResponse({'Status': False, 'Messege': str(error)})
                if order:
                    if order:
                        # Отправку сообщения в Email пришлось отключить из-за конфликта с почтой
                        # new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True})
                    return JsonResponse({'Status': True, 'Messege': f'Заказ {order_id} оформлен'})
                else:
                    return JsonResponse({'Status': False, 'Messege': f'Заказ {order_id} уже оформлен'})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы, '
                                                                'order_id и contact_id должны быть цифровыми'})
        else:
            return JsonResponse({'Status': False, 'Errors': 'Необходимо передать order_id и contact_id'})



