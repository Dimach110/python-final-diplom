"""orders URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from backend.views import ImportPrice, ShopView, ProductView, RegisterUser, LoginUser, RegisterPartner, Basket, \
    PartnerOrder, OrderView, ContactView, CategoryView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/shop', ShopView.as_view(), name='shops view'),
    path('api/v1/product', ProductView.as_view(), name='product view'),
    path('api/v1/import', ImportPrice.as_view(), name='import price'),
    path('api/v1/shop', ShopView.as_view(), name='add new shop'),
    path('api/v1/product', ProductView.as_view(), name='add new product'),
    path('api/v1/category', CategoryView.as_view(), name='category_view'),
    path('api/v1/user/registration', RegisterUser.as_view(), name='registration'),
    path('api/v1/user/login', LoginUser.as_view(), name='login user'),
    path('api/v1/user/contact', ContactView.as_view(), name='contact_user'),
    path('api/v1/user/contact/<int:contact_id>', ContactView.as_view(), name='contact_user'),
    path('api/v1/partner/import', ImportPrice.as_view(), name='import price'),
    path('api/v1/partner/registration', RegisterPartner.as_view(), name='registration Partner'),
    path('api/v1/user/basket', Basket.as_view(), name='basker_user'),
    path('api/v1/partner/order', PartnerOrder.as_view(), name='order_partner'),
    path('api/v1/partner/order/<order_id>', PartnerOrder.as_view(), name='order_partner'),
    path('api/v1/user/order', OrderView.as_view(), name='order_user'),

]
