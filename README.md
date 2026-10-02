# Backend — Gestión de Eventos (Django REST)

API REST para organizar eventos y sus gestiones (subtareas). Cada organizador inicia sesión con
correo y contraseña, recibe un token y solo puede ver y modificar sus propios eventos.

## Estructura

```
eventos/                  ← raíz Django (aquí vive manage.py)
├── eventos/              ← configuración del proyecto (settings, urls)
├── api/                  ← modelos, serializers, vistas y tests principales
├── health/               ← endpoint de salud para Render (/api/health)
└── requirements.txt      ← dependencias (UTF-8)
```

## Puesta en marcha local

```powershell
# 1. Entorno virtual (desde la raíz del repo)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r eventos\requirements.txt

# 3. Configuración: copia eventos\.env.example como eventos\.env y ajusta SECRET_KEY.
#    Si vas a usar la base de datos de Supabase, agrega DATABASE_URL.

# 4. Migraciones y servidor
cd eventos
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py runserver
```

- API: <http://localhost:8000/api/>
- Documentación interactiva (Swagger): <http://localhost:8000/api/docs/>

## Variables de entorno (`eventos/.env`)

| Variable | Descripción |
| --- | --- |
| `SECRET_KEY` | Obligatoria. Clave secreta de Django. |
| `DEBUG` | `True` en desarrollo; `False` en producción. |
| `ALLOWED_HOSTS` | Hosts permitidos, separados por coma. |
| `CSRF_TRUSTED_ORIGINS` | Orígenes confiables para CSRF. |
| `CORS_ALLOWED_ORIGINS` / `FRONTEND_URL` | Orígenes del frontend autorizados. |
| `DATABASE_URL` | Cadena de PostgreSQL (Supabase/Render). Si no se define, usa SQLite local. |

## Endpoints principales

| Método | Ruta | Autenticación | Descripción |
| --- | --- | --- | --- |
| POST | `/api/auth/registro/` | Pública | Crea la cuenta y devuelve token. |
| POST | `/api/auth/login/` | Pública | Devuelve el token del organizador. |
| POST | `/api/auth/logout/` | Token | Invalida el token actual. |
| GET | `/api/auth/me/` | Token | Datos del organizador autenticado. |
| GET/POST | `/api/eventos/` | Token | Lista (solo propios) o crea eventos. |
| GET/PUT/PATCH/DELETE | `/api/eventos/{id}/` | Token | Detalle y edición de un evento propio. |
| GET/POST | `/api/eventos/{id}/subtareas/` | Token | Gestiones de un evento propio. |
| GET/POST | `/api/subtareas/` | Token | Lista o crea gestiones propias. |
| GET/PUT/PATCH/DELETE | `/api/subtareas/{id}/` | Token | Detalle y edición de una gestión propia. |
| GET | `/api/hoy/` | Token | Gestiones agrupadas en `vencidas`, `para_hoy` y `proximas`, ordenadas por fecha y menor esfuerzo. Filtros: `?evento=<id>` y `?estado=abiertas\|pendiente\|en_progreso\|hecho\|todas`. |
| GET | `/api/health` | Pública | Salud del servicio (usada por Render). |
| GET | `/api/docs/` | Pública | Swagger UI. |

### Autenticación

```http
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

## Tests

```powershell
cd eventos
..\venv\Scripts\python.exe manage.py test
```

Los tests corren sobre SQLite local. Si tu `.env` apunta a Supabase, puedes forzar SQLite en la
sesión con `$env:DATABASE_URL="sqlite:///db-pruebas.sqlite3"` antes de ejecutarlos.

## Despliegue en Render

`render.yaml` define el servicio: `rootDir: eventos`, migraciones en el build y
`gunicorn eventos.wsgi:application`. Recuerda configurar `DATABASE_URL`, `SECRET_KEY`,
`DEBUG=False` y `FRONTEND_URL` en las variables de entorno del servicio.
