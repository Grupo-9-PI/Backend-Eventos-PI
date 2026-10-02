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

from .models import Evento, Subtarea
from .serializers import (
    EventoSerializer,
    LoginSerializer,
    RegistroSerializer,
    RespuestaAuthSerializer,
    RespuestaHoySerializer,
    SubtareaSerializer,
    UsuarioSerializer,
)

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
# Vista Hoy (C2 y C5)
# ---------------------------------------------------------------------------

class HoyView(APIView):
    @extend_schema(
        tags=['hoy'],
        summary='Gestiones agrupadas para la vista Hoy',
        description=(
            'Devuelve las gestiones del organizador autenticado agrupadas en **vencidas**, '
            '**para_hoy** y **proximas**, ya ordenadas para mostrar en la vista Hoy.\n\n'
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
        grupos = {
            'vencidas': [t for t in tareas if t.plazo < hoy],
            'para_hoy': [t for t in tareas if t.plazo == hoy],
            'proximas': [t for t in tareas if t.plazo > hoy],
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
