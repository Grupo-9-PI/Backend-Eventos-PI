from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventoViewSet, SubtareaViewSet

# El DefaultRouter crea automáticamente todas las rutas (GET, POST, PUT, DELETE) para tu vista
router = DefaultRouter()
router.register(r'eventos', EventoViewSet)
router.register(r'subtareas', SubtareaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]