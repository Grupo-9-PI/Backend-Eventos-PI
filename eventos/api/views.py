from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConfiguracionOrganizador, Evento, Subtarea
from .serializers import (
    ConfiguracionOrganizadorSerializer,
    ErrorConflictoSerializer,
    EventoSerializer,
    LoginSerializer,
    RegistroSerializer,
    ReprogramarTareaSerializer,
    ResolverConflictoRespuestaSerializer,
    ResolverConflictoSerializer,
    RespuestaAuthSerializer,
    RespuestaHoySerializer,
    SubtareaSerializer,
    UsuarioSerializer,
)

EJEMPLO_RESPUESTA_CONFLICTO = {
    "conflicto": True,
    "codigo": "SOBRECARGA_DIARIA",
    "mensaje": (
        "Sobrecarga de trabajo detectada para el día 2026-10-15. "
        "El límite diario es de 6.00h y con esta gestión acumularías 7.50h, superando el límite por 1.50h."
    ),
    "fecha": "2026-10-15",
    "limite_horas": "6.00",
    "horas_actuales": "5.00",
    "horas_nueva_gestion": "2.50",
    "horas_totales_proyectadas": "7.50",
    "horas_exceso": "1.50",
    "estrategias_disponibles": ["mover_otro_dia", "reducir_horas"],
    "fechas_sugeridas": [
        {"fecha": "2026-10-16", "horas_totales_proyectadas": "2.50"},
        {"fecha": "2026-10-17", "horas_totales_proyectadas": "2.50"},
        {"fecha": "2026-10-18", "horas_totales_proyectadas": "0.50"},
    ],
    "detalles": {
        "fecha": "2026-10-15",
        "limite_horas": "6.00",
        "horas_actuales": "5.00",
        "horas_nueva_gestion": "2.50",
        "horas_totales_proyectadas": "7.50",
        "horas_exceso": "1.50",
    },
}

EJEMPLO_RESPUESTA_RESOLUCION = {
    "resuelto": True,
    "mensaje": (
        "Conflicto resuelto. El 2026-10-16 queda con 2.50h planificadas de las 6.00h de límite diario."
    ),
    "subtarea": {
        "id": 7,
        "evento": 3,
        "gestion": "Confirmar menú con el catering",
        "categoria": "CATERING",
        "estado": "pendiente",
        "prioridad": "alta",
        "estimacion_horas": "2.50",
        "plazo": "2026-10-16",
        "hora_limite": "15:00:00",
        "hora_inicio": None,
    },
    "limite_horas": "6.00",
    "horas_totales_proyectadas": "2.50",
    "horas_exceso": "0.00",
    "fechas_sugeridas": [],
}

EJEMPLO_TAREA_VENCIDA = {
    "id": 12,
    "titulo": "Confirmar menú con el catering",
    "categoria": "CATERING",
    "estado": "pendiente",
    "prioridad": "alta",
    "fecha_limite": "2026-09-28",
    "hora_limite": "14:00:00",
    "hora_inicio": None,
    "estimacion_horas": "2.50",
    "evento": {"id": 3, "nombre": "Lanzamiento Q4"},
}

EJEMPLO_RESPUESTA_HOY = {
    "generado_en": "2026-10-01",
    "total": 3,
    "filtros": {"evento": None, "estado": "abiertas"},
    "grupos": {
        "vencidas": [EJEMPLO_TAREA_VENCIDA],
        "para_hoy": [
            {
                **EJEMPLO_TAREA_VENCIDA,
                "id": 13,
                "titulo": "Enviar invitaciones finales",
                "categoria": "INVITACIONES",
                "prioridad": "media",
                "fecha_limite": "2026-10-01",
                "hora_limite": "18:00:00",
                "estimacion_horas": "1.00",
            }
        ],
        "proximas": [
            {
                **EJEMPLO_TAREA_VENCIDA,
                "id": 14,
                "titulo": "Prueba de sonido",
                "categoria": "PROVEEDORES",
                "prioridad": "baja",
                "fecha_limite": "2026-10-05",
                "hora_limite": "10:00:00",
                "estimacion_horas": "3.00",
            }
        ],
    },
}


# ---------------------------------------------------------------------------
# Autenticación local
# ---------------------------------------------------------------------------

class RegistroView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['auth'],
        summary='Registrar un organizador',
        description='Crea la cuenta con nombre, correo y contraseña, y devuelve el token para iniciar sesión de inmediato.',
        request=RegistroSerializer,
        responses={201: RespuestaAuthSerializer},
        examples=[
            OpenApiExample(
                'Solicitud de registro',
                value={"nombre": "Ana Torres", "email": "ana@ejemplo.com", "password": "ClaveSegura123"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta del registro',
                value={
                    "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
                    "usuario": {"id": 1, "nombre": "Ana Torres", "email": "ana@ejemplo.com"},
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        token = Token.objects.create(user=usuario)
        return Response(
            {'token': token.key, 'usuario': UsuarioSerializer(usuario).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['auth'],
        summary='Iniciar sesión',
        description='Valida el correo y la contraseña y devuelve el token que debe enviarse como "Authorization: Token <token>".',
        request=LoginSerializer,
        responses={200: RespuestaAuthSerializer},
        examples=[
            OpenApiExample(
                'Solicitud de login',
                value={"email": "ana@ejemplo.com", "password": "ClaveSegura123"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta del login',
                value={
                    "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
                    "usuario": {"id": 1, "nombre": "Ana Torres", "email": "ana@ejemplo.com"},
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        usuario = serializer.validated_data['usuario']
        token, _ = Token.objects.get_or_create(user=usuario)
        return Response({'token': token.key, 'usuario': UsuarioSerializer(usuario).data})


class LogoutView(APIView):
    @extend_schema(
        tags=['auth'],
        summary='Cerrar sesión',
        description='Elimina el token del organizador autenticado.',
        request=None,
        responses={204: None},
    )
    def post(self, request):
        if request.auth:
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(
        tags=['auth'],
        summary='Consultar el organizador autenticado',
        responses={200: UsuarioSerializer},
    )
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Configuración del organizador (Límite diario de horas)
# ---------------------------------------------------------------------------

class ConfiguracionOrganizadorView(APIView):
    @extend_schema(
        tags=['configuracion'],
        summary='Consultar límite diario de horas del organizador',
        description=(
            'Devuelve el límite diario configurable de horas de gestión para el organizador autenticado. '
            'Por defecto es 6.00 horas.'
        ),
        responses={200: ConfiguracionOrganizadorSerializer},
        examples=[
            OpenApiExample(
                'Límite actual',
                value={"limite_diario_horas": "6.00"},
                response_only=True,
            )
        ],
    )
    def get(self, request):
        config, _ = ConfiguracionOrganizador.objects.get_or_create(usuario=request.user)
        return Response(ConfiguracionOrganizadorSerializer(config).data)

    @extend_schema(
        tags=['configuracion'],
        summary='Actualizar límite diario de horas del organizador',
        description='Actualiza el límite diario de horas de gestión para el organizador autenticado.',
        request=ConfiguracionOrganizadorSerializer,
        responses={
            200: ConfiguracionOrganizadorSerializer,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Definir nuevo límite a 8h',
                value={"limite_diario_horas": "8.00"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta de actualización',
                value={"limite_diario_horas": "8.00"},
                response_only=True,
            ),
        ],
    )
    def put(self, request):
        return self._guardar(request, partial=False)

    @extend_schema(
        tags=['configuracion'],
        summary='Actualizar parcialmente límite diario de horas',
        description='Actualiza parcialmente el límite diario de horas de gestión para el organizador autenticado.',
        request=ConfiguracionOrganizadorSerializer,
        responses={
            200: ConfiguracionOrganizadorSerializer,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Actualización parcial a 7.5h',
                value={"limite_diario_horas": "7.50"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta de actualización parcial',
                value={"limite_diario_horas": "7.50"},
                response_only=True,
            ),
        ],
    )
    def patch(self, request):
        return self._guardar(request, partial=True)

    def _guardar(self, request, partial=False):
        config, _ = ConfiguracionOrganizador.objects.get_or_create(usuario=request.user)
        serializer = ConfiguracionOrganizadorSerializer(config, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Vista Hoy (C2 y C5)
# ---------------------------------------------------------------------------

class HoyView(APIView):
    @extend_schema(
        tags=['hoy'],
        summary='Gestiones agrupadas para la vista Hoy',
        description=(
            'Devuelve las gestiones del organizador autenticado agrupadas en **vencidas** '
            '(fecha y hora límite ya pasadas), **para_hoy** (vence hoy y su hora aún no pasa) '
            'y **proximas**, ya ordenadas para mostrar en la vista Hoy.\n\n'
            '**Orden dentro de cada grupo:** primero la fecha límite más cercana; si dos gestiones '
            'comparten fecha, va primero la de menor esfuerzo estimado; ante un empate total se usa '
            'la hora límite.\n\n'
            '**Filtros:** `evento` limita a un evento propio y `estado` acepta `abiertas` (por '
            'defecto: pendientes y en progreso), `pendiente`, `en_progreso`, `hecho` o `todas`.'
        ),
        parameters=[
            OpenApiParameter(
                name='evento',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Id de un evento del organizador autenticado.',
                examples=[OpenApiExample('Filtrar por evento', value=3)],
            ),
            OpenApiParameter(
                name='estado',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=['abiertas', 'pendiente', 'en_progreso', 'hecho', 'todas'],
                default='abiertas',
                description='Estado de la gestión por el que se filtra.',
                examples=[
                    OpenApiExample('Solo pendientes', value='pendiente'),
                    OpenApiExample('Todas las gestiones', value='todas'),
                ],
            ),
        ],
        responses={200: RespuestaHoySerializer},
        examples=[
            OpenApiExample(
                'Respuesta agrupada',
                value=EJEMPLO_RESPUESTA_HOY,
                response_only=True,
            )
        ],
    )
    def get(self, request):
        hoy = timezone.localdate()
        ahora = timezone.localtime().time().replace(tzinfo=None)
        tareas = Subtarea.objects.filter(evento__propietario=request.user).select_related('evento')

        evento_id = request.query_params.get('evento')
        evento_filtrado = None
        if evento_id not in (None, ''):
            if not evento_id.isdigit():
                return Response(
                    {'evento': 'El filtro evento debe ser un número entero.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            evento_filtrado = int(evento_id)
            tareas = tareas.filter(evento_id=evento_filtrado)

        estado = request.query_params.get('estado', 'abiertas')
        if estado == 'abiertas':
            tareas = tareas.exclude(estado='hecho')
        elif estado == 'todas':
            pass
        elif estado in dict(Subtarea.OPCIONES_ESTADO):
            tareas = tareas.filter(estado=estado)
        else:
            return Response(
                {'estado': 'Estado inválido. Opciones: abiertas, pendiente, en_progreso, hecho, todas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Orden pedido por la regla de priorización: fecha, menor esfuerzo y hora límite.
        tareas = list(tareas.order_by('plazo', 'estimacion_horas', 'hora_limite'))
        vencidas, para_hoy, proximas = [], [], []
        for tarea in tareas:
            if tarea.plazo < hoy or (tarea.plazo == hoy and tarea.hora_limite < ahora):
                vencidas.append(tarea)
            elif tarea.plazo == hoy:
                para_hoy.append(tarea)
            else:
                proximas.append(tarea)
        grupos = {
            'vencidas': vencidas,
            'para_hoy': para_hoy,
            'proximas': proximas,
        }
        datos = {
            'generado_en': hoy,
            'total': len(tareas),
            'filtros': {'evento': evento_filtrado, 'estado': estado},
            'grupos': grupos,
        }
        return Response(RespuestaHoySerializer(datos).data)


# ---------------------------------------------------------------------------
# Eventos y gestiones (aislados por organizador)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers de validación de sobrecarga diaria
# ---------------------------------------------------------------------------

def _obtener_limite_organizador(usuario):
    """Devuelve el límite diario (Decimal) del organizador, creando su config si no existe."""
    config, _ = ConfiguracionOrganizador.objects.get_or_create(usuario=usuario)
    return config.limite_diario_horas


def _cifras_dia(usuario, fecha, estimacion_nueva, excluir_subtarea_id=None):
    """
    Calcula las cifras de carga de un día para el organizador.

    Solo cuentan las gestiones abiertas (se excluyen las hechas) y opcionalmente
    se ignora una gestión (la que se está reprogramando) para no contarla dos veces.
    """
    limite = _obtener_limite_organizador(usuario)
    qs = Subtarea.objects.filter(
        evento__propietario=usuario,
        plazo=fecha,
    ).exclude(estado='hecho')
    if excluir_subtarea_id is not None:
        qs = qs.exclude(pk=excluir_subtarea_id)

    horas_actuales = qs.aggregate(total=Sum('estimacion_horas'))['total'] or Decimal('0')
    estimacion_nueva = Decimal(str(estimacion_nueva))
    horas_proyectadas = horas_actuales + estimacion_nueva
    exceso = horas_proyectadas - limite

    return {
        'fecha': fecha,
        'limite_horas': limite,
        'horas_actuales': horas_actuales,
        'horas_nueva_gestion': estimacion_nueva,
        'horas_totales_proyectadas': horas_proyectadas,
        'horas_exceso': max(exceso, Decimal('0')),
    }


def _calcular_sobrecarga(usuario, fecha_nueva, estimacion_nueva, excluir_subtarea_id=None):
    """
    Devuelve las cifras del día si al asignar `estimacion_nueva` horas se supera
    el límite diario del organizador, o None si no hay sobrecarga.
    """
    cifras = _cifras_dia(usuario, fecha_nueva, estimacion_nueva, excluir_subtarea_id)
    return cifras if cifras['horas_exceso'] > 0 else None


def _sugerir_fechas(usuario, fecha_base, estimacion_nueva, excluir_subtarea_id=None,
                    horizonte_dias=90, maximo=3):
    """
    Sugiere días próximos en los que la gestión cabe sin superar el límite diario.

    Recorre desde el día siguiente a `fecha_base` hasta `horizonte_dias` y devuelve
    hasta `maximo` fechas con su carga total proyectada.
    """
    sugeridas = []
    for dias in range(1, horizonte_dias + 1):
        fecha = fecha_base + timedelta(days=dias)
        cifras = _cifras_dia(usuario, fecha, estimacion_nueva, excluir_subtarea_id)
        if cifras['horas_exceso'] <= 0:
            sugeridas.append({
                'fecha': fecha,
                'horas_totales_proyectadas': cifras['horas_totales_proyectadas'],
            })
            if len(sugeridas) >= maximo:
                break
    return sugeridas


# ---------------------------------------------------------------------------
# Eventos y gestiones (aislados por organizador)
# ---------------------------------------------------------------------------

class EventoViewSet(viewsets.ModelViewSet):
    # El atributo queryset permite a drf-spectacular tipar el parámetro id del esquema.
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer

    def get_queryset(self):
        return (
            Evento.objects.filter(propietario=self.request.user)
            .prefetch_related('subtareas')
            .order_by('id')
        )

    def perform_create(self, serializer):
        serializer.save(propietario=self.request.user)

    # Esta acción crea automáticamente la ruta GET/POST /api/eventos/<id>/subtareas/
    @extend_schema(
        tags=['eventos'],
        summary='Gestiones de un evento',
        description='Lista o crea gestiones dentro de un evento del organizador autenticado.',
    )
    @action(detail=True, methods=['get', 'post'])
    def subtareas(self, request, pk=None):
        evento = self.get_object()  # 404 si el evento es de otro organizador

        if request.method == 'GET':
            serializer = SubtareaSerializer(evento.subtareas.all(), many=True, context={'request': request})
            return Response(serializer.data)

        datos = request.data.copy()
        datos['evento'] = evento.id
        serializer = SubtareaSerializer(data=datos, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubtareaViewSet(viewsets.ModelViewSet):
    queryset = Subtarea.objects.all()
    serializer_class = SubtareaSerializer

    def get_queryset(self):
        return (
            Subtarea.objects.filter(evento__propietario=self.request.user)
            .select_related('evento')
            .order_by('id')
        )

    def perform_create(self, serializer):
        evento = serializer.validated_data['evento']
        if evento.propietario_id != self.request.user.id:
            raise PermissionDenied('No puedes agregar gestiones a un evento que no te pertenece.')
        serializer.save()

    @extend_schema(
        tags=['subtareas'],
        summary='Reprogramar una gestión (con detección de sobrecarga)',
        description=(
            'Cambia el plazo, hora límite y/o estimación de horas de una gestión.\n\n'
            '**Lógica de sobrecarga:** si la nueva fecha ya acumula más horas que el límite '
            'diario del organizador (configurable en `/api/config/`), el servidor **aborta la '
            'transacción** y devuelve `409 Conflict` con las cifras exactas del exceso para que '
            'el frontend pueda mostrar un diálogo de conflicto comprensible al usuario.\n\n'
            'El cálculo solo cuenta gestiones abiertas (excluye las hechas) y responde también '
            '**`fechas_sugeridas`**: días próximos en los que la gestión cabe sin superar el límite.\n\n'
            'Si no hay sobrecarga, persiste el cambio y devuelve la gestión actualizada.'
        ),
        request=ReprogramarTareaSerializer,
        responses={
            200: SubtareaSerializer,
            400: OpenApiTypes.OBJECT,
            409: ErrorConflictoSerializer,
        },
        examples=[
            OpenApiExample(
                'Reprogramar a otro día',
                value={"plazo": "2026-10-20", "hora_limite": "15:00"},
                request_only=True,
            ),
            OpenApiExample(
                'Reprogramar también con nueva estimación',
                value={"plazo": "2026-10-20", "hora_limite": "15:00", "estimacion_horas": "2.50"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta exitosa (sin conflicto)',
                value={
                    "id": 7,
                    "evento": 3,
                    "gestion": "Confirmar menú con el catering",
                    "categoria": "CATERING",
                    "estado": "pendiente",
                    "prioridad": "alta",
                    "estimacion_horas": "2.50",
                    "plazo": "2026-10-20",
                    "hora_limite": "15:00:00",
                    "hora_inicio": None,
                },
                response_only=True,
                status_codes=['200'],
            ),
            OpenApiExample(
                '409 Conflict — sobrecarga detectada',
                value=EJEMPLO_RESPUESTA_CONFLICTO,
                response_only=True,
                status_codes=['409'],
            ),
        ],
    )
    @action(detail=True, methods=['patch'], url_path='reprogramar')
    def reprogramar(self, request, pk=None):
        subtarea = self.get_object()  # 404 si es de otro organizador
        ser = ReprogramarTareaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        datos = ser.validated_data

        fecha_nueva = datos.get('plazo', subtarea.plazo)
        estimacion_nueva = datos.get('estimacion_horas', subtarea.estimacion_horas)

        # Verificar sobrecarga: excluimos la subtarea actual para no contarla dos veces
        conflicto = _calcular_sobrecarga(
            usuario=request.user,
            fecha_nueva=fecha_nueva,
            estimacion_nueva=estimacion_nueva,
            excluir_subtarea_id=subtarea.pk,
        )
        if conflicto:
            limite = conflicto['limite_horas']
            proyectadas = conflicto['horas_totales_proyectadas']
            exceso = conflicto['horas_exceso']
            cuerpo = {
                'conflicto': True,
                'codigo': 'SOBRECARGA_DIARIA',
                'mensaje': (
                    f"Sobrecarga detectada para el {fecha_nueva.strftime('%d/%m/%Y')}. "
                    f"Tu límite diario es de {limite}h y con esta gestión acumularías "
                    f"{proyectadas}h, superando el límite por {exceso}h. "
                    f"Elige una estrategia para resolver el conflicto."
                ),
                **conflicto,
                'estrategias_disponibles': ['mover_otro_dia', 'reducir_horas'],
                'fechas_sugeridas': _sugerir_fechas(
                    usuario=request.user,
                    fecha_base=fecha_nueva,
                    estimacion_nueva=estimacion_nueva,
                    excluir_subtarea_id=subtarea.pk,
                ),
            }
            return Response(cuerpo, status=status.HTTP_409_CONFLICT)

        # Sin conflicto: persistir el cambio atómicamente
        with transaction.atomic():
            if 'plazo' in datos:
                subtarea.plazo = datos['plazo']
            if 'hora_limite' in datos:
                subtarea.hora_limite = datos['hora_limite']
            if 'estimacion_horas' in datos:
                subtarea.estimacion_horas = datos['estimacion_horas']
            subtarea.save()

        return Response(SubtareaSerializer(subtarea, context={'request': request}).data)


# ---------------------------------------------------------------------------
# Reprogramar con fuerza / resolución de conflicto elegida por el usuario
# ---------------------------------------------------------------------------

class ResolverConflictoView(APIView):
    @extend_schema(
        tags=['subtareas'],
        summary='Resolver conflicto de sobrecarga con una estrategia',
        description=(
            'Aplica la estrategia elegida por el organizador para resolver el conflicto de '
            'sobrecarga detectado al reprogramar, y **recalcula** el día para confirmar el resultado.\n\n'
            '**Estrategias disponibles:**\n'
            '- `mover_otro_dia`: mueve la gestión al `plazo` indicado.\n'
            '- `reducir_horas`: cambia la `estimacion_horas` de la gestión al valor indicado; '
            'mantiene el plazo original.\n\n'
            'Si el conflicto persiste tras aplicar el cambio, la respuesta lo indica con '
            '`resuelto: false`, las nuevas cifras y `fechas_sugeridas` para seguir resolviendo.'
        ),
        request=ResolverConflictoSerializer,
        responses={
            200: ResolverConflictoRespuestaSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Estrategia: mover a otro día',
                value={"estrategia": "mover_otro_dia", "plazo": "2026-10-22", "hora_limite": "10:00"},
                request_only=True,
            ),
            OpenApiExample(
                'Estrategia: reducir horas',
                value={"estrategia": "reducir_horas", "estimacion_horas": "1.00"},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta con conflicto resuelto',
                value=EJEMPLO_RESPUESTA_RESOLUCION,
                response_only=True,
            ),
        ],
    )
    def post(self, request, pk):
        # Verificar que la gestión pertenece al organizador autenticado
        try:
            subtarea = Subtarea.objects.select_related('evento').get(
                pk=pk, evento__propietario=request.user
            )
        except Subtarea.DoesNotExist:
            return Response(
                {'detail': 'Gestión no encontrada o no te pertenece.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        ser = ResolverConflictoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        datos = ser.validated_data
        estrategia = datos['estrategia']

        with transaction.atomic():
            if estrategia == 'mover_otro_dia':
                if 'plazo' not in datos:
                    return Response(
                        {'plazo': "Se requiere 'plazo' para la estrategia 'mover_otro_dia'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                subtarea.plazo = datos['plazo']
                if 'hora_limite' in datos:
                    subtarea.hora_limite = datos['hora_limite']

            elif estrategia == 'reducir_horas':
                if 'estimacion_horas' not in datos:
                    return Response(
                        {'estimacion_horas': "Se requiere 'estimacion_horas' para la estrategia 'reducir_horas'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                subtarea.estimacion_horas = datos['estimacion_horas']

            subtarea.save()

        # Recalcular el día para confirmar si el conflicto quedó resuelto o persiste.
        cifras = _cifras_dia(
            usuario=request.user,
            fecha=subtarea.plazo,
            estimacion_nueva=subtarea.estimacion_horas,
            excluir_subtarea_id=subtarea.pk,
        )
        resuelto = cifras['horas_exceso'] <= 0
        if resuelto:
            mensaje = (
                f"Conflicto resuelto. El {subtarea.plazo.strftime('%d/%m/%Y')} queda con "
                f"{cifras['horas_totales_proyectadas']}h planificadas de las "
                f"{cifras['limite_horas']}h de límite diario."
            )
        else:
            mensaje = (
                f"El conflicto persiste: el {subtarea.plazo.strftime('%d/%m/%Y')} quedaría con "
                f"{cifras['horas_totales_proyectadas']}h planificadas, superando el límite de "
                f"{cifras['limite_horas']}h por {cifras['horas_exceso']}h."
            )

        cuerpo = {
            'resuelto': resuelto,
            'mensaje': mensaje,
            'subtarea': SubtareaSerializer(subtarea, context={'request': request}).data,
            'limite_horas': cifras['limite_horas'],
            'horas_totales_proyectadas': cifras['horas_totales_proyectadas'],
            'horas_exceso': cifras['horas_exceso'],
            'fechas_sugeridas': [],
        }
        if not resuelto:
            cuerpo['fechas_sugeridas'] = _sugerir_fechas(
                usuario=request.user,
                fecha_base=subtarea.plazo,
                estimacion_nueva=subtarea.estimacion_horas,
                excluir_subtarea_id=subtarea.pk,
            )
        return Response(cuerpo)
