from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.products, name='products'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('products/<int:pk>/archive/', views.archive_product, name='archive_product'),
    path('products/<int:pk>/unarchive/', views.unarchive_product, name='unarchive_product'),

    # Categories
    path('categories/', views.categories, name='categories'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<int:pk>/edit/', views.edit_category, name='edit_category'),

    # POS
    path('pos/', views.pos, name='pos'),
    path('api/process-sale/', views.process_sale, name='process_sale'),

    # Purchase
    path('purchase/', views.purchase, name='purchase'),

    # Reports
    path('reports/', views.reports, name='reports'),

    # Users (Owner only)
    path('users/', views.users, name='users'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:pk>/deactivate/', views.deactivate_user, name='deactivate_user'),
    path('users/<int:pk>/activate/', views.activate_user, name='activate_user'),

    # Credit / Utang
    path('credit/', views.credit_list, name='credit_list'),
    path('credit/<int:pk>/add-payment/', views.credit_add_payment, name='credit_add_payment'),
    path('credit/<int:pk>/delete/', views.credit_delete, name='credit_delete'),

    # Client Management (Superuser only)
    path('clients/', views.client_list, name='client_list'),
    path('clients/add/', views.client_add, name='client_add'),
    path('clients/<int:pk>/edit/', views.client_edit, name='client_edit'),

    # API
    path('api/products/', views.api_products, name='api_products'),
]