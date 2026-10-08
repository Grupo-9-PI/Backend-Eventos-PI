from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import ConfiguracionOrganizador, Evento, Subtarea

Usuario = get_user_model()

CLAVE = 'ClaveSegura123'


class BaseAPITest(APITestCase):
    def crear_usuario(self, email, nombre='Usuario'):
        return Usuario.objects.create_user(
            username=email,
            email=email,
            first_name=nombre,
            password=CLAVE,
        )

    def autenticar(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def crear_evento(self, propietario, nombre='Evento de prueba', **kwargs):
        hoy = timezone.localdate()
        datos = {
            'propietario': propietario,
            'nombre': nombre,
            'tipo': 'Lanzamiento',
            'lugar': 'Auditorio principal',
            'fecha_inicio': hoy + timedelta(days=30),
            'fecha_final': hoy + timedelta(days=30),
            'hora': '10:00',
            'duracion_horas': '4.00',
            'limite_diario_horas': '8.00',
        }
        datos.update(kwargs)
        return Evento.objects.create(**datos)

    def crear_tarea(self, evento, plazo, estimacion='2.00', estado='pendiente', titulo='Gestión', hora='12:00'):
        return Subtarea.objects.create(
            evento=evento,
            gestion=titulo,
            categoria='OTRO',
            estado=estado,
            prioridad='media',
            estimacion_horas=estimacion,
            plazo=plazo,
            hora_limite=hora,
        )


class AutenticacionTests(BaseAPITest):
    def test_api_sin_token_responde_401(self):
        for url in ['/api/eventos/', '/api/subtareas/', '/api/hoy/']:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_registro_crea_usuario_y_devuelve_token(self):
        respuesta = self.client.post(
            '/api/auth/registro/',
            {'nombre': 'Ana Torres', 'email': 'ana@ejemplo.com', 'password': CLAVE},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertIn('token', respuesta.data)
        self.assertEqual(respuesta.data['usuario']['nombre'], 'Ana Torres')
        self.assertTrue(Usuario.objects.filter(username='ana@ejemplo.com').exists())

    def test_registro_rechaza_correo_duplicado(self):
        self.crear_usuario('ana@ejemplo.com')
        respuesta = self.client.post(
            '/api/auth/registro/',
            {'nombre': 'Otra Ana', 'email': 'ANA@ejemplo.com', 'password': CLAVE},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('email', respuesta.data)

    def test_registro_rechaza_contrasena_debil(self):
        respuesta = self.client.post(
            '/api/auth/registro/',
            {'nombre': 'Ana', 'email': 'ana@ejemplo.com', 'password': '12345678'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('password', respuesta.data)

    def test_login_valido_devuelve_token(self):
        usuario = self.crear_usuario('ana@ejemplo.com', 'Ana')
        respuesta = self.client.post(
            '/api/auth/login/',
            {'email': 'ana@ejemplo.com', 'password': CLAVE},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['token'], Token.objects.get(user=usuario).key)

    def test_login_invalido_responde_401(self):
        self.crear_usuario('ana@ejemplo.com')
        respuesta = self.client.post(
            '/api/auth/login/',
            {'email': 'ana@ejemplo.com', 'password': 'incorrecta123'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data['detail'], 'Credenciales inválidas.')

    def test_me_devuelve_el_organizador_autenticado(self):
        usuario = self.crear_usuario('ana@ejemplo.com', 'Ana')
        self.autenticar(usuario)
        respuesta = self.client.get('/api/auth/me/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['email'], 'ana@ejemplo.com')
        self.assertEqual(respuesta.data['nombre'], 'Ana')

    def test_logout_elimina_el_token(self):
        usuario = self.crear_usuario('ana@ejemplo.com')
        self.autenticar(usuario)
        respuesta = self.client.post('/api/auth/logout/')
        self.assertEqual(respuesta.status_code, 204)
        self.assertFalse(Token.objects.filter(user=usuario).exists())


class AislamientoTests(BaseAPITest):
    def setUp(self):
        self.ana = self.crear_usuario('ana@ejemplo.com', 'Ana')
        self.beto = self.crear_usuario('beto@ejemplo.com', 'Beto')
        self.evento_ana = self.crear_evento(self.ana, 'Evento de Ana')
        self.tarea_ana = self.crear_tarea(self.evento_ana, timezone.localdate(), titulo='Gestión de Ana')

    def test_listado_solo_muestra_eventos_propios(self):
        self.crear_evento(self.beto, 'Evento de Beto')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/eventos/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([e['nombre'] for e in respuesta.data], ['Evento de Ana'])

    def test_detalle_de_evento_ajeno_responde_404(self):
        self.autenticar(self.beto)
        respuesta = self.client.get(f'/api/eventos/{self.evento_ana.id}/')
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_editar_ni_eliminar_evento_ajeno(self):
        self.autenticar(self.beto)
        self.assertEqual(self.client.patch(f'/api/eventos/{self.evento_ana.id}/', {'nombre': 'Hackeado'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/eventos/{self.evento_ana.id}/').status_code, 404)

    def test_no_puede_listar_gestiones_de_evento_ajeno(self):
        self.autenticar(self.beto)
        respuesta = self.client.get(f'/api/eventos/{self.evento_ana.id}/subtareas/')
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_crear_gestion_en_evento_ajeno(self):
        self.autenticar(self.beto)
        respuesta = self.client.post(
            '/api/subtareas/',
            {
                'evento': self.evento_ana.id,
                'gestion': 'Intrusa',
                'categoria': 'OTRO',
                'estimacion_horas': '1.00',
                'plazo': str(timezone.localdate()),
                'hora_limite': '09:00',
            },
            format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_puede_ver_gestiones_ajenas_en_el_listado_global(self):
        self.autenticar(self.beto)
        respuesta = self.client.get('/api/subtareas/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, [])

    def test_crear_evento_asigna_el_propietario_de_la_sesion(self):
        self.autenticar(self.ana)
        hoy = timezone.localdate()
        respuesta = self.client.post(
            '/api/eventos/',
            {
                'nombre': 'Evento nuevo',
                'tipo': 'Lanzamiento',
                'lugar': 'Salón',
                'fecha_inicio': str(hoy + timedelta(days=10)),
                'fecha_final': str(hoy + timedelta(days=10)),
                'hora': '18:00',
                'duracion_horas': '3.00',
                'limite_diario_horas': '8.00',
                'notas_produccion': '',
            },
            format='json',
        )
        self.assertEqual(respuesta.status_code, 201)
        evento = Evento.objects.get(nombre='Evento nuevo')
        self.assertEqual(evento.propietario, self.ana)
        # El cliente no puede falsificar el dueño enviando el campo.
        self.assertEqual(respuesta.data['propietario'], self.ana.id)


FECHA_FIJA = date(2030, 1, 15)
AHORA_FIJA = datetime(2030, 1, 15, 12, 0)


class HoyTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        # Reloj fijo para que la agrupación por fecha y hora sea determinista.
        self.parche_fecha = mock.patch('api.views.timezone.localdate', return_value=FECHA_FIJA)
        self.parche_hora = mock.patch(
            'api.views.timezone.localtime',
            return_value=timezone.make_aware(AHORA_FIJA),
        )
        self.parche_fecha.start()
        self.parche_hora.start()
        self.addCleanup(self.parche_fecha.stop)
        self.addCleanup(self.parche_hora.stop)

        self.ana = self.crear_usuario('ana@ejemplo.com', 'Ana')
        self.beto = self.crear_usuario('beto@ejemplo.com', 'Beto')
        self.evento = self.crear_evento(
            self.ana,
            'Evento de Ana',
            fecha_inicio=FECHA_FIJA + timedelta(days=30),
            fecha_final=FECHA_FIJA + timedelta(days=30),
        )
        self.vencida_grande = self.crear_tarea(
            self.evento, FECHA_FIJA - timedelta(days=2), '5.00',
            titulo='Vencida grande', hora='11:00',
        )
        self.vencida_pequena = self.crear_tarea(
            self.evento, FECHA_FIJA - timedelta(days=2), '1.00',
            titulo='Vencida pequeña', hora='11:00',
        )
        self.vencida_de_hoy = self.crear_tarea(
            self.evento, FECHA_FIJA, '2.00',
            titulo='Ya pasó su hora', hora='10:00',
        )
        self.de_hoy = self.crear_tarea(
            self.evento, FECHA_FIJA, '2.00',
            titulo='Para hoy', hora='18:00',
        )
        self.proxima = self.crear_tarea(
            self.evento, FECHA_FIJA + timedelta(days=3), '2.00',
            titulo='Próxima', hora='12:00',
        )

    def test_agrupa_por_fecha_y_hora_y_ordena_por_esfuerzo(self):
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        self.assertEqual(respuesta.status_code, 200)
        grupos = respuesta.data['grupos']
        self.assertEqual(
            [t['titulo'] for t in grupos['vencidas']],
            ['Vencida pequeña', 'Vencida grande', 'Ya pasó su hora'],
        )
        self.assertEqual([t['titulo'] for t in grupos['para_hoy']], ['Para hoy'])
        self.assertEqual([t['titulo'] for t in grupos['proximas']], ['Próxima'])
        self.assertEqual(respuesta.data['total'], 5)
        self.assertEqual(respuesta.data['filtros'], {'evento': None, 'estado': 'abiertas'})

    def test_incluye_datos_del_evento_en_cada_tarea(self):
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        tarea = respuesta.data['grupos']['para_hoy'][0]
        self.assertEqual(tarea['evento'], {'id': self.evento.id, 'nombre': 'Evento de Ana'})

    def test_excluye_las_hechas_por_defecto(self):
        self.crear_tarea(self.evento, FECHA_FIJA, estado='hecho', titulo='Terminada', hora='18:00')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        self.assertEqual(respuesta.data['total'], 5)

    def test_filtra_por_estado(self):
        self.crear_tarea(self.evento, FECHA_FIJA, estado='hecho', titulo='Terminada', hora='18:00')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/', {'estado': 'hecho'})
        self.assertEqual([t['titulo'] for t in respuesta.data['grupos']['para_hoy']], ['Terminada'])
        respuesta = self.client.get('/api/hoy/', {'estado': 'todas'})
        self.assertEqual(respuesta.data['total'], 6)

    def test_filtra_por_evento(self):
        otro_evento = self.crear_evento(
            self.ana,
            'Otro evento',
            fecha_inicio=FECHA_FIJA + timedelta(days=30),
            fecha_final=FECHA_FIJA + timedelta(days=30),
        )
        self.crear_tarea(otro_evento, FECHA_FIJA, titulo='De otro evento', hora='18:00')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/', {'evento': otro_evento.id})
        self.assertEqual(respuesta.data['total'], 1)
        self.assertEqual(respuesta.data['filtros']['evento'], otro_evento.id)

    def test_estado_invalido_responde_400(self):
        self.autenticar(self.ana)
        self.assertEqual(self.client.get('/api/hoy/', {'estado': 'loquesea'}).status_code, 400)

    def test_evento_no_numerico_responde_400(self):
        self.autenticar(self.ana)
        self.assertEqual(self.client.get('/api/hoy/', {'evento': 'abc'}).status_code, 400)

    def test_no_muestra_gestiones_de_otros_organizadores(self):
        evento_beto = self.crear_evento(
            self.beto,
            'Evento de Beto',
            fecha_inicio=FECHA_FIJA + timedelta(days=30),
            fecha_final=FECHA_FIJA + timedelta(days=30),
        )
        self.crear_tarea(evento_beto, FECHA_FIJA, titulo='De Beto', hora='18:00')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/', {'estado': 'todas'})
        self.assertEqual(respuesta.data['total'], 5)
        titulos = [
            t['titulo']
            for grupo in respuesta.data['grupos'].values()
            for t in grupo
        ]
        self.assertNotIn('De Beto', titulos)


# ---------------------------------------------------------------------------
# Tests: Configuración del organizador (límite diario)
# ---------------------------------------------------------------------------

class ConfiguracionTests(BaseAPITest):
    def setUp(self):
        self.ana = self.crear_usuario('ana@test.com', 'Ana')
        self.autenticar(self.ana)

    def test_get_config_devuelve_limite_default_6h(self):
        respuesta = self.client.get('/api/config/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['limite_diario_horas'], '6.00')

    def test_put_config_actualiza_limite(self):
        respuesta = self.client.put('/api/config/', {'limite_diario_horas': '8.00'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['limite_diario_horas'], '8.00')
        config = ConfiguracionOrganizador.objects.get(usuario=self.ana)
        self.assertEqual(str(config.limite_diario_horas), '8.00')

    def test_patch_config_actualiza_limite(self):
        respuesta = self.client.patch('/api/config/', {'limite_diario_horas': '4.50'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['limite_diario_horas'], '4.50')

    def test_config_rechaza_limite_cero(self):
        respuesta = self.client.put('/api/config/', {'limite_diario_horas': '0'}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_config_rechaza_limite_negativo(self):
        respuesta = self.client.put('/api/config/', {'limite_diario_horas': '-1'}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_config_rechaza_limite_mayor_a_24h(self):
        respuesta = self.client.put('/api/config/', {'limite_diario_horas': '25'}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_config_requiere_token(self):
        self.client.credentials()
        respuesta = self.client.get('/api/config/')
        self.assertEqual(respuesta.status_code, 401)

    def test_me_incluye_limite_diario_horas(self):
        """El endpoint /api/auth/me/ ahora expone el límite del organizador."""
        respuesta = self.client.get('/api/auth/me/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('limite_diario_horas', respuesta.data)


# ---------------------------------------------------------------------------
# Tests: Reprogramar una gestión con detección de sobrecarga (409)
# ---------------------------------------------------------------------------

DIA_REPROGRAM = date(2030, 3, 10)


class ReprogramarTests(BaseAPITest):
    def setUp(self):
        self.ana = self.crear_usuario('ana@test.com', 'Ana')
        self.autenticar(self.ana)
        # Establecer límite diario a 6h
        ConfiguracionOrganizador.objects.update_or_create(
            usuario=self.ana, defaults={'limite_diario_horas': '6.00'}
        )
        self.evento = self.crear_evento(
            self.ana,
            fecha_inicio=DIA_REPROGRAM + timedelta(days=30),
            fecha_final=DIA_REPROGRAM + timedelta(days=30),
        )
        # Gestión existente en el día objetivo: 5h
        self.otra = self.crear_tarea(self.evento, DIA_REPROGRAM, estimacion='5.00', titulo='Existente')
        # Gestión a reprogramar (en otro día): 2h
        self.gestion = self.crear_tarea(
            self.evento,
            DIA_REPROGRAM + timedelta(days=5),
            estimacion='2.00',
            titulo='A reprogramar',
        )

    def test_reprogramar_sin_conflicto_persiste_y_devuelve_200(self):
        """Mover a un día vacío: OK."""
        dia_libre = DIA_REPROGRAM + timedelta(days=10)
        respuesta = self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(dia_libre), 'hora_limite': '10:00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.gestion.refresh_from_db()
        self.assertEqual(self.gestion.plazo, dia_libre)

    def test_reprogramar_con_sobrecarga_devuelve_409_con_cifras(self):
        """Mover al día que ya tiene 5h (límite 6h) + 2h propias = 7h → 409."""
        respuesta = self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(DIA_REPROGRAM), 'hora_limite': '10:00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(respuesta.data['conflicto'])
        self.assertEqual(respuesta.data['codigo'], 'SOBRECARGA_DIARIA')
        # Las cifras exactas deben estar en la respuesta
        self.assertIn('horas_actuales', respuesta.data)
        self.assertIn('horas_exceso', respuesta.data)
        self.assertIn('horas_totales_proyectadas', respuesta.data)
        self.assertIn('estrategias_disponibles', respuesta.data)
        self.assertIn('mover_otro_dia', respuesta.data['estrategias_disponibles'])
        self.assertIn('reducir_horas', respuesta.data['estrategias_disponibles'])

    def test_reprogramar_409_no_modifica_la_gestion(self):
        """Tras un 409 la gestión debe quedar sin cambios en BD."""
        plazo_original = self.gestion.plazo
        self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(DIA_REPROGRAM)},
            format='json',
        )
        self.gestion.refresh_from_db()
        self.assertEqual(self.gestion.plazo, plazo_original)

    def test_reprogramar_con_reduccion_evita_conflicto(self):
        """Mover al día cargado pero reduciendo a 0.5h (total 5.5h < 6h) → 200."""
        respuesta = self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(DIA_REPROGRAM), 'estimacion_horas': '0.50'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_reprogramar_requiere_token(self):
        self.client.credentials()
        respuesta = self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(DIA_REPROGRAM)},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_reprogramar_no_aplica_a_gestion_ajena(self):
        beto = self.crear_usuario('beto@test.com', 'Beto')
        self.autenticar(beto)
        respuesta = self.client.patch(
            f'/api/subtareas/{self.gestion.id}/reprogramar/',
            {'plazo': str(DIA_REPROGRAM + timedelta(days=10))},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 404)


# ---------------------------------------------------------------------------
# Tests: Resolución de conflicto de sobrecarga
# ---------------------------------------------------------------------------

class ResolverConflictoTests(BaseAPITest):
    def setUp(self):
        self.ana = self.crear_usuario('ana@test.com', 'Ana')
        self.autenticar(self.ana)
        ConfiguracionOrganizador.objects.update_or_create(
            usuario=self.ana, defaults={'limite_diario_horas': '6.00'}
        )
        self.evento = self.crear_evento(
            self.ana,
            fecha_inicio=DIA_REPROGRAM + timedelta(days=30),
            fecha_final=DIA_REPROGRAM + timedelta(days=30),
        )
        self.gestion = self.crear_tarea(
            self.evento, DIA_REPROGRAM, estimacion='3.00', titulo='A resolver'
        )

    def test_estrategia_mover_otro_dia_persiste_nueva_fecha(self):
        nuevo_dia = DIA_REPROGRAM + timedelta(days=2)
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'mover_otro_dia', 'plazo': str(nuevo_dia), 'hora_limite': '09:00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.gestion.refresh_from_db()
        self.assertEqual(self.gestion.plazo, nuevo_dia)

    def test_estrategia_reducir_horas_persiste_nueva_estimacion(self):
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'reducir_horas', 'estimacion_horas': '1.00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.gestion.refresh_from_db()
        self.assertEqual(str(self.gestion.estimacion_horas), '1.00')

    def test_mover_otro_dia_sin_plazo_devuelve_400(self):
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'mover_otro_dia'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_reducir_horas_sin_estimacion_devuelve_400(self):
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'reducir_horas'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_resolver_conflicto_de_gestion_ajena_devuelve_404(self):
        beto = self.crear_usuario('beto@test.com', 'Beto')
        self.autenticar(beto)
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'reducir_horas', 'estimacion_horas': '1.00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_resolver_conflicto_requiere_token(self):
        self.client.credentials()
        respuesta = self.client.post(
            f'/api/subtareas/{self.gestion.id}/resolver-conflicto/',
            {'estrategia': 'reducir_horas', 'estimacion_horas': '1.00'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 401)

