from rest_framework import serializers
from .models import Evento, Subtarea

class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        # '__all__' le indica a Django que traduzca todos los campos que creaste en el modelo
        fields = '__all__'

    # Esta función intercepta los datos antes de guardarlos
    def validate(self, data):
        # 1. Validar fechas lógicas
        if data['fecha_inicio'] > data['fecha_final']:
            raise serializers.ValidationError({
                "fecha_final": "La fecha final no puede ser anterior a la fecha de inicio."
            })
        
        # 2. Validar duración positiva
        if data['duracion_horas'] <= 0:
            raise serializers.ValidationError({
                "duracion_horas": "La duración del evento debe ser mayor a 0 horas."
            })

        return data

class SubtareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtarea
        fields = '__all__'