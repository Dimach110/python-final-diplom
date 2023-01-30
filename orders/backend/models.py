from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


STATUS_CHOICES = (
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('seller', 'Продавец'),
    ('buyer', 'Покупатель'),

)

class UserManager(BaseUserManager):
    """Создаём модель управляющего"""
    def create_user(self, email, password=None, **other_fields):
        # Создаём Email и нормализуем переводя доменную часть в нижний регистр
        email = self.normalize_email(email)
        user = self.model(email=email, **other_fields)
        if not password:
            password = self.make_random_password()
        user = self.model(email=email, **other_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **other_fields):
        other_fields.setdefault('is_staff', False)
        other_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **other_fields)

    def create_superuser(self, email, password, **other_fields):
        other_fields.setdefault('is_staff', True)
        other_fields.setdefault('is_superuser', True)

        if other_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if other_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **other_fields)

class User(AbstractUser):
    """Создаём модель пользователя для клиентов"""
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = 'email'
    email = models.EmailField(_('email address'), unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _('username'),
        max_length=150,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    type = models.CharField(verbose_name='Тип пользователя', choices=USER_TYPE_CHOICES, max_length=5, default='buyer')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)
#
class Shop(models.Model):
    name = models.CharField(max_length=64, verbose_name='Название магазина')
    url = models.URLField(verbose_name="Ссылка", null=True, blank=True)
    address = models.CharField(max_length=128, verbose_name="Адрес магазина", null=True, blank=True)

    state = models.BooleanField(verbose_name="Статус", default=True)

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Список магазинов"
        ordering = ("-name",)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=64, verbose_name="Название категории")
    shops = models.ManyToManyField(Shop, verbose_name="Магазины", blank=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Список категорий"
        ordering = ("-name",)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=80, verbose_name="Название")
    category = models.ForeignKey(Category, verbose_name="Категория", blank=True,
                                 related_name="products", on_delete=models.CASCADE)
    brand = models.CharField(max_length=16, verbose_name="Производитель")
    model = models.CharField(max_length=16, verbose_name="Модель")


    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Список продуктов"
        ordering = ("-name",)

    def __str__(self):
        return self.name

class ProductInfo(models.Model):
    product = models.ForeignKey(Product, verbose_name="Продукт", related_name="products",
                                blank=True, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, verbose_name="Магазин", related_name="products_info", blank=True,
                             on_delete=models.CASCADE)
    description = models.CharField(max_length=256, verbose_name="Описание", null=True, blank=True)
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.PositiveIntegerField(verbose_name="Цена")
    price_rrc = models.PositiveIntegerField(verbose_name="Рекомендуемая розначная цена")

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Информациz продуктах"
        constraints = [models.UniqueConstraint(fields=['product', 'shop'], name='unique_product_info')]

    def __str__(self):
        return self.product

class Parameter(models.Model):
    name = models.CharField(max_length=32, verbose_name="Имя параметра")

    class Meta:
        verbose_name = 'Имя параметра'
        verbose_name_plural = "Список имен параметров"
        ordering = ('-name',)

    def __str__(self):
        return self.name

class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, verbose_name="Информация о продукте",
                                     related_name="products_parameters", blank=True, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, verbose_name="Параметр", related_name="products_parameters",
                                  blank=True, on_delete=models.CASCADE)
    value = models.CharField(max_length=64, verbose_name="Значение")

class Order(models.Model):
    user = models.ForeignKey(User, verbose_name="Заказчик", related_name="orders",
                             blank=True, on_delete=models.CASCADE)
    contact = models.ForeignKey("Contact", verbose_name="Контакты", related_name="orders",
                             blank=True, on_delete=models.CASCADE)
    date_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=25, verbose_name="Статус заказа", choices=STATUS_CHOICES)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказов"
        ordering = ('-date_time', "-user",)

    def __str__(self):
        return str(self.date_time)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", blank=True, related_name="orders_items",
                              on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Продукт", blank=True, related_name="orders_items",
                                on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, verbose_name="Магазин", blank=True, related_name="orders_items",
                                on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name="Количество")

class Contact(models.Model):
    user = models.ForeignKey(User, verbose_name="Покупатель", related_name="contacts", blank=True,
                             on_delete=models.CASCADE)
    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=100, verbose_name='Улица')
    house = models.CharField(max_length=15, verbose_name='Дом')
    structure = models.CharField(max_length=15, verbose_name='Корпус', blank=True)
    building = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон')

    class Meta:
        verbose_name = 'Контакты пользователя'
        verbose_name_plural = "Список контактов пользователей"

    def __str__(self):
        return f'Город:{self.city}\nУлица:{self.street}\nДом:{self.house}\nТелефон:{self.phone}'

