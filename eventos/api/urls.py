from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'eventos', views.EventoViewSet, basename='evento')
router.register(r'subtareas', views.SubtareaViewSet, basename='subtarea')

urlpatterns = [
    path('auth/registro/', views.RegistroView.as_view(), name='registro'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('hoy/', views.HoyView.as_view(), name='hoy'),
    path('', include(router.urls)),
]
