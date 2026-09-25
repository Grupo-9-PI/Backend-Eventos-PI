from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Ruta invisible que genera la estructura de la base de datos
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # La interfaz visual interactiva de Swagger
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # La conexión a tus endpoints
    path('api/',  include('api.urls')),
    path('api/', include('health.urls')),
]


