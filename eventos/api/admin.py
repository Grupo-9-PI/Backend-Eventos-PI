from django.contrib import admin

from .models import Evento, Subtarea


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
