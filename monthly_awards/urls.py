from django.urls import path
from .views import (
    monthly_awards_list,
    add_monthly_award,
    edit_monthly_award,
    delete_monthly_award
)

urlpatterns = [
    path('', monthly_awards_list, name='monthly_awards_list'),
    path('add/', add_monthly_award, name='add_monthly_award'),
    path('edit/<int:pk>/', edit_monthly_award, name='edit_monthly_award'),
    path('delete/<int:pk>/', delete_monthly_award, name='delete_monthly_award'),
]