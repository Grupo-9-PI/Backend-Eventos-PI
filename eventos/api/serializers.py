from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDeDjango
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .models import Evento, Subtarea

Usuario = get_user_model()


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

class UsuarioSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='first_name')

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email']


class RegistroSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        email = value.strip().lower()
        if Usuario.objects.filter(username__iexact=email).exists():
            raise serializers.ValidationError("Ya existe una cuenta registrada con este correo.")
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except ErrorDeDjango as error:
            raise serializers.ValidationError(list(error.messages))
        return value

    def create(self, validated_data):
        # Usamos el correo como nombre de usuario para simplificar el login local.
        return Usuario.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data['nombre'],
            password=validated_data['password'],
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        usuario = authenticate(
            request=self.context.get('request'),
            username=attrs['email'].strip().lower(),
            password=attrs['password'],
        )
        if usuario is None:
            raise AuthenticationFailed('Credenciales inválidas.')
        attrs['usuario'] = usuario
        return attrs


class RespuestaAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    usuario = UsuarioSerializer()


# ---------------------------------------------------------------------------
# Eventos y gestiones
# ---------------------------------------------------------------------------

class SubtareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtarea
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un organizador solo puede asociar gestiones a sus propios eventos.
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated:
            self.fields['evento'].queryset = Evento.objects.filter(propietario=request.user)

    def validate(self, data):
        estimacion = data.get('estimacion_horas', getattr(self.instance, 'estimacion_horas', None))
        if estimacion is not None and estimacion <= 0:
            raise serializers.ValidationError({"estimacion_horas": "La estimación debe ser mayor a 0 horas."})

        evento = data.get('evento', getattr(self.instance, 'evento', None))
        plazo = data.get('plazo', getattr(self.instance, 'plazo', None))
        if evento is not None and plazo is not None and plazo > evento.fecha_inicio:
            raise serializers.ValidationError({"plazo": "El plazo de la gestión debe ser anterior o igual al inicio del evento."})

        return data


class EventoSerializer(serializers.ModelSerializer):
    subtareas = SubtareaSerializer(many=True, read_only=True)

    class Meta:
        model = Evento
        fields = '__all__'
        # El dueño se asigna siempre desde la sesión, nunca desde el cliente.
        read_only_fields = ['propietario', 'creado_en']

    def validate(self, data):
        inicio = data.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        final = data.get('fecha_final', getattr(self.instance, 'fecha_final', None))
        if inicio is not None and final is not None and inicio > final:
            raise serializers.ValidationError({
                "fecha_final": "La fecha final no puede ser anterior a la fecha de inicio."
            })

        duracion = data.get('duracion_horas', getattr(self.instance, 'duracion_horas', None))
        if duracion is not None and duracion <= 0:
            raise serializers.ValidationError({
                "duracion_horas": "La duración del evento debe ser mayor a 0 horas."
            })

        limite = data.get('limite_diario_horas', getattr(self.instance, 'limite_diario_horas', None))
        if limite is not None and limite <= 0:
            raise serializers.ValidationError({
                "limite_diario_horas": "El límite diario debe ser mayor a 0 horas."
            })

        return data


# ---------------------------------------------------------------------------
# Vista Hoy
# ---------------------------------------------------------------------------

class EventoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = ['id', 'nombre']


class TareaHoySerializer(serializers.ModelSerializer):
    titulo = serializers.CharField(source='gestion')
    fecha_limite = serializers.DateField(source='plazo')
    evento = EventoResumenSerializer(read_only=True)

    class Meta:
        model = Subtarea
        fields = [
            'id',
            'titulo',
            'categoria',
            'estado',
            'prioridad',
            'fecha_limite',
            'hora_limite',
            'hora_inicio',
            'estimacion_horas',
            'evento',
        ]


class GruposHoySerializer(serializers.Serializer):
    vencidas = TareaHoySerializer(many=True)
    para_hoy = TareaHoySerializer(many=True)
    proximas = TareaHoySerializer(many=True)


class FiltrosHoySerializer(serializers.Serializer):
    evento = serializers.IntegerField(allow_null=True)
    estado = serializers.CharField()


class RespuestaHoySerializer(serializers.Serializer):
    generado_en = serializers.DateField()
    total = serializers.IntegerField()
    filtros = FiltrosHoySerializer()
    grupos = GruposHoySerializer()
