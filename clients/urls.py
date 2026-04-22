from django.urls import path
from . import views

urlpatterns = [
    path('', views.clients_list, name='clients_list'),
    path('add/', views.client_add, name='client_add'),
    path('<int:pk>/edit/', views.client_edit, name='client_edit'),
    path('<int:pk>/delete/', views.client_delete, name='client_delete'),
    path('autocomplete/', views.client_autocomplete, name='client_autocomplete'),
    # Contact URLs
    path('<int:client_pk>/contacts/', views.contact_list, name='contact_list'),
    path('<int:client_pk>/contacts/add/', views.contact_add, name='contact_add'),
    path('<int:client_pk>/contacts/<int:contact_pk>/edit/', views.contact_edit, name='contact_edit'),
    path('<int:client_pk>/contacts/<int:contact_pk>/delete/', views.contact_delete, name='contact_delete'),
    # Contacts API
    path('<int:client_pk>/contacts-api/', views.client_contacts_api, name='client_contacts_api'),
]
