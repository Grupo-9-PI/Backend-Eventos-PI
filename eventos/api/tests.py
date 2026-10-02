from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Evento, Subtarea

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

    def crear_tarea(self, evento, plazo, estimacion='2.00', estado='pendiente', titulo='Gestión'):
        return Subtarea.objects.create(
            evento=evento,
            gestion=titulo,
            categoria='OTRO',
            estado=estado,
            prioridad='media',
            estimacion_horas=estimacion,
            plazo=plazo,
            hora_limite='12:00',
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


class HoyTests(BaseAPITest):
    def setUp(self):
        self.ana = self.crear_usuario('ana@ejemplo.com', 'Ana')
        self.beto = self.crear_usuario('beto@ejemplo.com', 'Beto')
        self.evento = self.crear_evento(self.ana, 'Evento de Ana')
        hoy = timezone.localdate()
        self.vencida_grande = self.crear_tarea(self.evento, hoy - timedelta(days=2), '5.00', titulo='Vencida grande')
        self.vencida_pequena = self.crear_tarea(self.evento, hoy - timedelta(days=2), '1.00', titulo='Vencida pequeña')
        self.de_hoy = self.crear_tarea(self.evento, hoy, '2.00', titulo='Para hoy')
        self.proxima = self.crear_tarea(self.evento, hoy + timedelta(days=3), '2.00', titulo='Próxima')

    def test_agrupa_y_ordena_por_fecha_y_esfuerzo(self):
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        self.assertEqual(respuesta.status_code, 200)
        grupos = respuesta.data['grupos']
        self.assertEqual(
            [t['titulo'] for t in grupos['vencidas']],
            ['Vencida pequeña', 'Vencida grande'],
        )
        self.assertEqual([t['titulo'] for t in grupos['para_hoy']], ['Para hoy'])
        self.assertEqual([t['titulo'] for t in grupos['proximas']], ['Próxima'])
        self.assertEqual(respuesta.data['total'], 4)
        self.assertEqual(respuesta.data['filtros'], {'evento': None, 'estado': 'abiertas'})

    def test_incluye_datos_del_evento_en_cada_tarea(self):
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        tarea = respuesta.data['grupos']['para_hoy'][0]
        self.assertEqual(tarea['evento'], {'id': self.evento.id, 'nombre': 'Evento de Ana'})

    def test_excluye_las_hechas_por_defecto(self):
        self.crear_tarea(self.evento, timezone.localdate(), estado='hecho', titulo='Terminada')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/')
        self.assertEqual(respuesta.data['total'], 4)

    def test_filtra_por_estado(self):
        self.crear_tarea(self.evento, timezone.localdate(), estado='hecho', titulo='Terminada')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/', {'estado': 'hecho'})
        self.assertEqual([t['titulo'] for t in respuesta.data['grupos']['para_hoy']], ['Terminada'])
        respuesta = self.client.get('/api/hoy/', {'estado': 'todas'})
        self.assertEqual(respuesta.data['total'], 5)

    def test_filtra_por_evento(self):
        otro_evento = self.crear_evento(self.ana, 'Otro evento')
        self.crear_tarea(otro_evento, timezone.localdate(), titulo='De otro evento')
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
        evento_beto = self.crear_evento(self.beto, 'Evento de Beto')
        self.crear_tarea(evento_beto, timezone.localdate(), titulo='De Beto')
        self.autenticar(self.ana)
        respuesta = self.client.get('/api/hoy/', {'estado': 'todas'})
        titulos = [t['titulo'] for t in respuesta.data['grupos']['para_hoy']]
        self.assertNotIn('De Beto', titulos)
