from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'eventos', views.EventoViewSet, basename='evento')
router.register(r'subtareas', views.SubtareaViewSet, basename='subtarea')

urlpatterns = [
    # Auth
    path('auth/registro/', views.RegistroView.as_view(), name='registro'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    # Configuración del organizador (límite diario de horas) — GET / PUT / PATCH
    path('config/', views.ConfiguracionOrganizadorView.as_view(), name='config'),

    # Vista Hoy
    path('hoy/', views.HoyView.as_view(), name='hoy'),

    # Resolución de conflicto de sobrecarga para una gestión específica
    # POST /api/subtareas/<pk>/resolver-conflicto/
    path(
        'subtareas/<int:pk>/resolver-conflicto/',
        views.ResolverConflictoView.as_view(),
        name='resolver-conflicto',
    ),

    # Viewsets (incluye la action PATCH /api/subtareas/<pk>/reprogramar/)
    path('', include(router.urls)),
]
