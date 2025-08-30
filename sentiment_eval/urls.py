"""
URL configuration for sentiment_eval project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'reviews', views.ReviewViewSet)
router.register(r'sentences', views.ReviewSentenceViewSet)
router.register(r'evaluations', views.HumanEvaluationViewSet, basename='evaluation')
router.register(r'sessions', views.EvaluationSessionViewSet, basename='session')
router.register(r'upload-logs', views.DataUploadLogViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    
    
    # API Root - must be first
    path('', views.api_root, name='api-root'),
    
    # Authentication endpoints
    path('auth/register/', views.register_user, name='register'),
    path('auth/login/', views.login_user, name='login'),
    path('auth/logout/', views.logout_user, name='logout'),
    path('auth/user/', views.current_user, name='current-user'),
    
    # Data management endpoints
    path('data/upload-csv/', views.upload_csv, name='upload-csv'),
    path('data/validate-csv/', views.validate_csv, name='validate-csv'),
    path('data/export-evaluations/', views.export_evaluations, name='export-evaluations'),
    
    # Analytics endpoints
    path('analytics/model-performance/', views.model_performance_stats, name='model-performance'),
    path('analytics/evaluator-agreement/', views.evaluator_agreement, name='evaluator-agreement'),
    path('analytics/dashboard/', views.dashboard_stats, name='dashboard-stats'),
    
    # Include router URLs - this should be last
    path('api/', include(router.urls)),
]
