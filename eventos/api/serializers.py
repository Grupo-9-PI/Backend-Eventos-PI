from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDeDjango
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .models import ConfiguracionOrganizador, Evento, Subtarea

Usuario = get_user_model()


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

class UsuarioSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='first_name')
    limite_diario_horas = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'limite_diario_horas']

    @extend_schema_field(serializers.CharField())
    def get_limite_diario_horas(self, obj):
        config = getattr(obj, 'configuracion', None)
        if config is None:
            config, _ = ConfiguracionOrganizador.objects.get_or_create(usuario=obj)
        return str(config.limite_diario_horas)


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


# ---------------------------------------------------------------------------
# Configuración del organizador (Límite diario de horas)
# ---------------------------------------------------------------------------

class ConfiguracionOrganizadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionOrganizador
        fields = ['limite_diario_horas']

    def validate_limite_diario_horas(self, value):
        if value <= 0:
            raise serializers.ValidationError("El límite diario debe ser mayor a 0 horas.")
        if value > 24:
            raise serializers.ValidationError("El límite diario no puede superar las 24 horas.")
        return value


# ---------------------------------------------------------------------------
# Reprogramación y resolución de conflictos de sobrecarga
# ---------------------------------------------------------------------------

class ReprogramarTareaSerializer(serializers.Serializer):
    plazo = serializers.DateField(
        help_text="Nueva fecha límite (plazo) para la gestión (YYYY-MM-DD)."
    )
    hora_limite = serializers.TimeField(
        required=False,
        help_text="Nueva hora límite (opcional)."
    )
    estimacion_horas = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        help_text="Nueva estimación de horas (opcional, debe ser > 0)."
    )

    def validate_estimacion_horas(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("La estimación debe ser mayor a 0 horas.")
        return value


class ResolverConflictoSerializer(serializers.Serializer):
    estrategia = serializers.ChoiceField(
        choices=[
            ('mover_otro_dia', 'Mover a otro día'),
            ('reducir_horas', 'Reducir horas estimadas'),
        ],
        help_text="Estrategia seleccionada para resolver el conflicto de sobrecarga.",
    )
    plazo = serializers.DateField(
        required=False,
        help_text="Nueva fecha si la estrategia es 'mover_otro_dia' (YYYY-MM-DD).",
    )
    hora_limite = serializers.TimeField(
        required=False,
        help_text="Nueva hora límite (opcional).",
    )
    estimacion_horas = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        help_text="Horas estimadas reducidas si la estrategia es 'reducir_horas'.",
    )

    def validate_estimacion_horas(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("La estimación debe ser mayor a 0 horas.")
        return value


class DetalleConflictoSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    limite_horas = serializers.DecimalField(max_digits=4, decimal_places=2)
    horas_actuales = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_nueva_gestion = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_totales_proyectadas = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_exceso = serializers.DecimalField(max_digits=5, decimal_places=2)


class ErrorConflictoSerializer(serializers.Serializer):
    conflicto = serializers.BooleanField(default=True)
    codigo = serializers.CharField(default="SOBRECARGA_DIARIA")
    mensaje = serializers.CharField()
    fecha = serializers.DateField()
    limite_horas = serializers.DecimalField(max_digits=4, decimal_places=2)
    horas_actuales = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_nueva_gestion = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_totales_proyectadas = serializers.DecimalField(max_digits=5, decimal_places=2)
    horas_exceso = serializers.DecimalField(max_digits=5, decimal_places=2)
    estrategias_disponibles = serializers.ListField(child=serializers.CharField())
    detalles = DetalleConflictoSerializer(required=False)

