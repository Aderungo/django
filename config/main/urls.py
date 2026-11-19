from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import PasswordChangeStyledForm

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<slug:slug>/', views.dish_detail, name='dish_detail'),
    path('calculator/', views.calculator, name='calculator'),
    path('checkout/', views.checkout, name='checkout'),
    path('contacts/', views.contacts, name='contacts'),

    path('account/', views.account, name='account'),
    path('account/orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('account/orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('account/orders/<int:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('account/orders/<int:pk>/print/', views.order_print, name='order_print'),
    path('account/orders/<int:pk>/review/', views.review_create, name='review_create'),

    path('register/', views.register, name='register'),
    path('login/', views.SiteLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='main:index'), name='logout'),
    path('password/', auth_views.PasswordChangeView.as_view(
        template_name='main/password_change.html',
        form_class=PasswordChangeStyledForm,
        success_url='/account/',
    ), name='password_change'),

    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/orders/', views.manager_orders, name='manager_orders'),
    path('manager/orders.csv', views.manager_orders_csv, name='manager_orders_csv'),
    path('manager/orders/<int:pk>/status/', views.manager_order_status, name='manager_order_status'),
    path('manager/dishes/add/', views.dish_create, name='dish_create'),
    path('manager/dishes/<int:pk>/edit/', views.dish_update, name='dish_update'),
    path('manager/dishes/<int:pk>/delete/', views.dish_delete, name='dish_delete'),

    path('api/dishes/', views.api_dishes, name='api_dishes'),
    path('api/calculator/', views.api_calculator, name='api_calculator'),
]
