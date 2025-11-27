from django.urls import path
from .views import (
    sales_tracker,
    add_sales_enquiry,
    edit_sales_enquiry,
    delete_sales_enquiry,
    sales_tracker_poll
)

urlpatterns = [
    path('', sales_tracker, name='sales_tracker'),
    path('add/', add_sales_enquiry, name='add_sales_enquiry'),
    path('edit/<int:pk>/', edit_sales_enquiry, name='edit_sales_enquiry'),
    path('delete/<int:pk>/', delete_sales_enquiry, name='delete_sales_enquiry'),
    path('api/poll/', sales_tracker_poll, name='sales_tracker_poll'),
]