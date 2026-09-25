from rest_framework import serializers
from .models import Evento, Subtarea

class SubtareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtarea
        fields = '__all__'

    def validate(self, data):
        if 'estimacion_horas' in data and data['estimacion_horas'] <= 0:
            raise serializers.ValidationError({"estimacion_horas": "La estimación debe ser mayor a 0 horas."})
        
        # Opcional: Validar que el plazo de la tarea no supere la fecha de inicio del evento
        if 'plazo' in data and 'evento' in data:
            evento = data['evento']
            if data['plazo'] > evento.fecha_inicio:
                raise serializers.ValidationError({"plazo": "El plazo de la gestión debe ser anterior o igual al inicio del evento."})
        
        return data

class EventoSerializer(serializers.ModelSerializer):
    subtareas = SubtareaSerializer(many=True, read_only=True)

    class Meta:
        model = Evento
        # '__all__' le indica a Django que traduzca todos los campos que creaste en el modelo
        fields = '__all__'

    # Esta función intercepta los datos antes de guardarlos
    def validate(self, data):
        # 1. Validar fechas lógicas
        if 'fecha_inicio' in data and 'fecha_final' in data:
            if data['fecha_inicio'] > data['fecha_final']:
                raise serializers.ValidationError({
                    "fecha_final": "La fecha final no puede ser anterior a la fecha de inicio."
                })
        
        # 2. Validar duración positiva
        if 'duracion_horas' in data and data['duracion_horas'] <= 0:
            raise serializers.ValidationError({
                "duracion_horas": "La duración del evento debe ser mayor a 0 horas."
            })

        # 3. Validar límite diario positivo
        if 'limite_diario_horas' in data and data['limite_diario_horas'] <= 0:
            raise serializers.ValidationError({
                "limite_diario_horas": "El límite diario debe ser mayor a 0 horas."
            })

        return data
