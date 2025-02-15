from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.tokens import get_token_generator

STATUS_CHOICES = (
    ('new', 'новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
    ('basket', 'В корзине')
)

USER_TYPE_CHOICES = (
    ('seller', 'Продавец'),
    ('buyer', 'Покупатель'),

)

class UserManager(BaseUserManager):
    """Модель УЗ менеджера"""
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
    """Модель пользователя для клиентов"""
    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = 'email'
    surname = models.CharField(verbose_name='Фамилия', max_length=30, blank=True)
    email = models.EmailField(_('email address'), unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _('username'),
        max_length=150,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={'unique': _("A user with that username already exists."),},)
    is_active = models.BooleanField(_('active'), default=False, help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'),)
    type = models.CharField(verbose_name='Тип пользователя', choices=USER_TYPE_CHOICES, max_length=12, default='buyer')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)


class ConfirmEmailToken(models.Model):
    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'

    # не очень понял зачем нужен декоратор преобразующий статический метод в метод
    @staticmethod
    def generate_key():
        return get_token_generator().generate_token()

    user = models.ForeignKey(
        User,
        related_name='confirm_email_tokens',
        on_delete=models.CASCADE,
        verbose_name=_("The User which is associated to this password reset token")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("When was this token generated")
    )

    # Ключ для проверки (высылается на Email пользователя)
    key = models.CharField(
        _("Key"),
        max_length=64,
        db_index=True,
        unique=True
    )

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return "Password reset token for user {user}".format(user=self.user)

class Shop(models.Model):
    name = models.CharField(max_length=64, verbose_name='Название магазина')
    url = models.URLField(verbose_name="Ссылка", null=True, blank=True)
    address = models.CharField(max_length=128, verbose_name="Адрес магазина", null=True, blank=True)
    user = models.OneToOneField(User, verbose_name='Пользователь',
                                blank=True, null=True, related_name='shops',
                                on_delete=models.CASCADE)
    state = models.BooleanField(verbose_name="Статус", default=True)

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Список магазинов"
        ordering = ("-name",)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=64, verbose_name="Название категории")
    shop = models.ManyToManyField(Shop, verbose_name="Магазины", blank=True)

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



    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Список продуктов"
        ordering = ("-name",)

    def __str__(self):
        return self.name

class ProductInfo(models.Model):
    product = models.ForeignKey(Product, verbose_name="Продукт", related_name="product_info",
                                blank=True, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, verbose_name="Магазин", related_name="product_info", blank=True,
                             on_delete=models.CASCADE)
    model = models.CharField(max_length=128, verbose_name="Производитель/Модель", null=True, blank=True)
    description = models.CharField(max_length=256, verbose_name="Описание", null=True, blank=True)
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.PositiveIntegerField(verbose_name="Цена")
    price_rrc = models.PositiveIntegerField(verbose_name="Рекомендуемая розничная цена")

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = "Информация о продуктах"
        constraints = [models.UniqueConstraint(fields=['product', 'shop'], name='unique_product_info')]

    # def __str__(self):
    #     return self.product

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
                                     related_name="product_parameters", blank=True, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, verbose_name="Параметр", related_name="products_parameters",
                                  blank=True, on_delete=models.CASCADE)
    value = models.CharField(max_length=64, verbose_name="Значение")

class Order(models.Model):
    user = models.ForeignKey(User, verbose_name="Заказчик", related_name="orders",
                             blank=True, on_delete=models.CASCADE)
    contact = models.ForeignKey("Contact", verbose_name="Контакты", related_name="orders",
                                blank=True, null=True, on_delete=models.CASCADE)
    date_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=25, verbose_name="Статус заказа", choices=STATUS_CHOICES)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказов"
        ordering = ('-date_time', "-user",)

    def __str__(self):
        return str(f' order id: {self.id}, date created: {self.date_time}')

class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", blank=True, related_name="ordered_items",
                              on_delete=models.CASCADE)
    product_info = models.ForeignKey(ProductInfo, verbose_name="Продукт", blank=True, related_name="ordered_items",
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

