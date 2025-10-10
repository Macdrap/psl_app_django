from django.urls import path
from .views import (
    invoiced_jobs_list,
    add_invoiced_job,
    edit_invoiced_job,
    add_invoice_to_award,
    delete_invoiced_job
)

urlpatterns = [
    path('', invoiced_jobs_list, name='invoiced_jobs_list'),
    path('add/', add_invoiced_job, name='add_invoiced_job'),
    path('edit/<int:pk>/', edit_invoiced_job, name='edit_invoiced_job'),
    path('invoiced-jobs/<int:pk>/delete/', delete_invoiced_job, name='delete_invoiced_job'),
    path('awards/<int:award_pk>/add-invoice/', add_invoice_to_award, name='add_invoice_to_award'),
]