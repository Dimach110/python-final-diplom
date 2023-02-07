from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from django.http import JsonResponse
from requests import get
from django.http import HttpRequest, JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import load as load_yaml, Loader
from ujson import loads as load_json
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from backend.models import Shop, ProductInfo, Product, Parameter, ProductParameter, Category
from backend.serializers import ProductSerializer, ShopSerializer, UserSerializer



class ShopView(APIView):

    def get(self, request, *args, **kwargs):
        """Просмотр всех магазинов"""
        queryset = Shop.objects.all()
        serializer = ShopSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление нового магазина"""
        data = request.data
        serializer = ShopSerializer(data=data)
        try:
            res = Shop.objects.get(name=data['name'])
        except:
            res = None
        if res == None:
            if serializer.is_valid():
                serializer.save()
                return JsonResponse(serializer.data)
            elif not serializer.is_valid():
                return Response(serializer.errors)
        else:
            return Response(f"Ошибка. Такой магазин уже существует с id {res.id} , укажите другое название")


class ProductView(APIView):

    def get(self, request, *args, **kwargs):
        """Просмотр всех продуктов"""
        queryset = Product.objects.all()
        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)

    # Подумать над возможностью добавления нескольких продуктов разом
    # Загнать функцию в цикл
    def post(self, request, *args, **kwargs):
        """Добавление новых продуктов"""
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
            return Response(f"Ошибка. Такой продукт уже существует с id {res.id} , укажите другое название")




class ImportPrice(APIView):
    # pass
    """Загрузка (импорт) списка продуктов"""

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': '403',
                                 'Error': 'Ошибка аутентификации пользователя'},
                                status=403)
        # if request.user.type != 'shop':
        #     return JsonResponse({'Status': '403',
        #                          'Error': 'Загрузку может осуществлять только продавец'},
        #                         status=403)

        url = request.data.get('url')

        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                stream = get(url).content

                data = load_yaml(stream, Loader=Loader)

                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
                for category in data['categories']:
                    category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
                    category_object.shops.add(shop.id)
                    category_object.save()
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

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

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

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
                    JsonResponse({"Status": False, "Errors": "Пользователь заблокирован, обратитесь к Администратору" })
            else:
                return JsonResponse({"Status": False, "Errors": 'Не правильно введён логин или пароль'})
        else:
            return JsonResponse({"Status": False,
                                 "Errors": "Не указаны необходимые аргументы ('email:' и 'password:')"})

class RegisterUser(APIView):

    """Регистрация новых пользователей"""
    def post(self, request):
        # проверяем что введены все необходимые данные (email, pass)
        if {'first_name', 'last_name', 'email', 'password'}.issubset(request.data):

        # Проводим проверку на сложность пароля
            try:
                validate_password(request.data['password'])
            except:
                # в дальнейшем доработать вывод типов ошибки
                return Response("Ваш пароль не соответствует требованиям безопасности")
            request.data.update({})
            user_serializer = UserSerializer(data=request.data)
            if user_serializer.is_valid(): # Если прошла проверка сериалайзером, то сохраняем
                user = user_serializer.save(is_active=True)
                user.set_password(request.data['password'])
                user.save()
        # вот тут не совсем понял зачем это?
        #         new_user_registered.send(sender=self.__class__, user_id=user.id)
                return JsonResponse({'Status': True, "Message": "Регистрация прошла успешно"})

            else:
                return JsonResponse({'Status': False, 'Errors': user_serializer.errors})
        else:
            return JsonResponse({"Status": False, "Error": "Не введены все требуемые для регистрации данные"})

class RegisterPartner(APIView):

    def post(self, request):
        print(request)
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            user_serializer = UserSerializer(data=request.data)
            if user_serializer.is_valid():
                user = user_serializer.save(is_active=True, type='seller')
                user.set_password(request.data['password'])
                user.save()
            return JsonResponse({'Status': True, "Message": "Регистрация прошла успешно"})

        else:
            return JsonResponse({"Status": False, "Error": "Не введены все требуемые для регистрации данные"})

