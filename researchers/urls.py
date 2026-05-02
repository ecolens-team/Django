from django.urls import path
from .views import (
    ResearcherStatsView,
    ResearcherQueueView,
    ResearcherReportsView,
    ResolveReportView,
    ResearcherInsightsView,
    ResearcherAlertsView,
    ResearcherExportView,
    SubmitObservationReportView,
)

urlpatterns = [
    path('stats/',                          ResearcherStatsView.as_view(),       name='researcher-stats'),
    path('queue/',                          ResearcherQueueView.as_view(),        name='researcher-queue'),
    path('reports/',                        ResearcherReportsView.as_view(),      name='researcher-reports'),
    path('reports/<int:pk>/resolve/',       ResolveReportView.as_view(),          name='researcher-resolve-report'),
    path('insights/',                       ResearcherInsightsView.as_view(),     name='researcher-insights'),
    path('alerts/',                         ResearcherAlertsView.as_view(),       name='researcher-alerts'),
    path('export/',                         ResearcherExportView.as_view(),       name='researcher-export'),
    path('observations/<int:observation_id>/report/', SubmitObservationReportView.as_view(), name='submit-report'),
]
