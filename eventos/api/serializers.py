from rest_framework import serializers
from .models import Evento, Subtarea

class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        # '__all__' le indica a Django que traduzca todos los campos que creaste en el modelo
        fields = '__all__'

class SubtareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtarea
        fields = '__all__'