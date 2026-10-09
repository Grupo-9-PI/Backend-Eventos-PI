from django.contrib import admin

from .models import Evento, Subtarea, ConfiguracionOrganizador


@admin.register(ConfiguracionOrganizador)
class ConfiguracionOrganizadorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'limite_diario_horas', 'actualizado_en')
    search_fields = ('usuario__username', 'usuario__email')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'propietario', 'tipo', 'fecha_inicio', 'fecha_final', 'creado_en')
    list_filter = ('tipo', 'propietario')
    search_fields = ('nombre', 'lugar')


@admin.register(Subtarea)
class SubtareaAdmin(admin.ModelAdmin):
    list_display = ('gestion', 'evento', 'categoria', 'estado', 'prioridad', 'plazo', 'estimacion_horas')
    list_filter = ('estado', 'prioridad', 'categoria')
    search_fields = ('gestion',)
