from django.urls import path
from .views import StatisticExplorerView, StatisticExplorerPDFView

urlpatterns = [
    path('', StatisticExplorerView.as_view(), name="statistic_explorer"),
    path('export/pdf/', StatisticExplorerPDFView.as_view(), name="statistic_explorer_pdf"),
]