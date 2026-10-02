# Cumplimiento de criterios por Sprint — Backend

Este documento describe, para el repositorio **Backend-Eventos-PI**, todo lo que ya está
implementado y verificado en relación con los criterios de los sprints 0, 1 y 2. La rama de
trabajo es `feature/sprint-auth-hoy`.

Rama de integración en el frontend: `feature/sprint-hoy-wiring` (documentada en su propio
`CUMPLIMIENTO-SPRINTS.md`).

---

## Cómo levantar y verificar

```powershell
# Desde la raíz del repo
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r eventos\requirements.txt

# Configuración: copia eventos\.env.example como eventos\.env y define SECRET_KEY.
# Para Supabase/Render agrega DATABASE_URL (Postgres).

cd eventos
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py runserver
```

- API: <http://localhost:8000/api/>
- Swagger: <http://localhost:8000/api/docs/>
- Salud: <http://localhost:8000/api/health>

Tests (siempre sobre SQLite local, sin tocar la base compartida):

```powershell
$env:DATABASE_URL="sqlite:///db-pruebas.sqlite3"
..\venv\Scripts\python.exe manage.py test
```

---

## Sprint 0 — Base técnica y arquitectura

### C3 — Tareas núcleo T1–T4 (soporte backend)

| Tarea núcleo | Soporte en este repo |
| --- | --- |
| T1 · Crear evento y gestiones logísticas | `POST /api/eventos/`, `POST /api/subtareas/` y `POST /api/eventos/{id}/subtareas/`; modelos `Evento` 1–N `Subtarea` con borrado en cascada. |
| T2 · Gestiones urgentes del día | `GET /api/hoy/` agrupa y ordena; la vista Hoy del frontend lo consume. |
| T3 · Reprogramar proveedores y sobrecarga | `PATCH/PUT /api/subtareas/{id}/` con validación de plazo y estimación. |
| T4 · Barra de progreso | El evento viaja con sus `subtareas` anidadas y su estado (`pendiente`, `en_progreso`, `hecho`) para calcular el porcentaje. |

### C5 — Arquitectura de información mínima (rutas del API)

| Método | Ruta | Auth | Descripción |
| --- | --- | --- | --- |
| POST | `/api/auth/registro/` | Pública | Crea cuenta y devuelve token. |
| POST | `/api/auth/login/` | Pública | Devuelve token del organizador. |
| POST | `/api/auth/logout/` | Token | Invalida el token actual. |
| GET | `/api/auth/me/` | Token | Datos del organizador autenticado. |
| GET/POST | `/api/eventos/` | Token | Lista (solo propios) o crea eventos. |
| GET/PUT/PATCH/DELETE | `/api/eventos/{id}/` | Token | Detalle y edición de un evento propio. |
| GET/POST | `/api/eventos/{id}/subtareas/` | Token | Gestiones de un evento propio. |
| GET/POST | `/api/subtareas/` | Token | Lista o crea gestiones propias. |
| GET/PUT/PATCH/DELETE | `/api/subtareas/{id}/` | Token | Detalle y edición de una gestión propia. |
| GET | `/api/hoy/` | Token | Gestiones agrupadas y ordenadas. Filtros `?evento=` y `?estado=`. |
| GET | `/api/health` | Pública | Salud del servicio (usada por Render). |
| GET | `/api/docs/` · `/api/schema/` | Pública | Swagger y OpenAPI. |

### C7 — Base técnica operativa (repo + FE + API + BD)

- API REST con **Django 6 + Django REST Framework**, documentada con **drf-spectacular**.
- Base de datos **PostgreSQL** (Supabase en desarrollo, Render en producción) con **migraciones
  versionadas** (`api/migrations/0001` a `0006`); SQLite como respaldo local.
- Despliegue con `render.yaml`: `rootDir: eventos`, instalación de `requirements.txt`,
  `collectstatic` + `migrate` en el build y `gunicorn` como servidor.
- Endpoint de salud en `/api/health` para el chequeo de Render.
- `requirements.txt` en UTF-8 con dependencias directas fijadas.

---

## Sprint 1 — Flujo end-to-end y calidad

### C1 — Crear evento + subtareas persistidas (React → DRF → BD)

- Endpoints transaccionales por separado y anidados (`/api/eventos/{id}/subtareas/`); el servidor
  inyecta el evento al crear una gestión anidada.
- Integridad a nivel de modelo: FK `Subtarea.evento` con `on_delete=CASCADE`.
- Evidencia: `api/tests.py` (creación, validaciones y consultas) y prueba de humo real contra
  Postgres/Supabase (registro → evento → gestión → `/api/hoy/`).

### C2 — Validaciones backend con mensajes claros

`EventoSerializer` y `SubtareaSerializer` validan también en actualizaciones parciales (PATCH):

| Regla | Mensaje |
| --- | --- |
| Fecha final no anterior a la inicial | "La fecha final no puede ser anterior a la fecha de inicio." |
| Duración del evento > 0 | "La duración del evento debe ser mayor a 0 horas." |
| Límite diario > 0 | "El límite diario debe ser mayor a 0 horas." |
| Estimación > 0 | "La estimación debe ser mayor a 0 horas." |
| Plazo ≤ inicio del evento | "El plazo de la gestión debe ser anterior o igual al inicio del evento." |
| Credenciales inválidas | "Credenciales inválidas." |
| Correo duplicado | "Ya existe una cuenta registrada con este correo." |

### C3 — API DRF documentada

- `/api/docs/` (Swagger UI) con **ejemplos completos de request/response** para cada endpoint de
  autenticación, eventos, gestiones y `/api/hoy/`, incluyendo códigos 201, 400 y 401.
- `/api/schema/` (OpenAPI 3) validado sin errores ni advertencias.
- Descripción global que aclara qué rutas requieren token y cuáles son públicas.

### C6 — Trabajo con dueño y trazabilidad (soporte)

- Commits atómicos por historia y migraciones versionadas; cada criterio puede rastrearse a los
  cambios del repositorio y a los tests que lo cubren.

---

## Sprint 2 — Login local y vista Hoy

### C1 — Login local, rutas protegidas y aislamiento por organizador

- Autenticación **por token** de DRF (`rest_framework.authtoken`), sin dependencias extra.
- `Evento.propietario` (FK obligatoria a `auth.User`); migración en tres pasos para bases con datos
  previos (`0004` agrega nullable → `0005` limpia huérfanos → `0006` la vuelve obligatoria).
- Aislamiento estricto:
  - `EventoViewSet` y `SubtareaViewSet` filtran el queryset por `request.user`.
  - El dueño se asigna desde la sesión (`perform_create`), nunca desde el cliente.
  - El campo `evento` al crear una gestión solo acepta eventos del propio organizador.
  - Las rutas anidadas responden 404 sobre eventos ajenos.
- Contraseñas con validadores de Django; el correo es el nombre de usuario.
- Cobertura: `AutenticacionTests` y `AislamientoTests` (un organizador no ve ni modifica datos del
  otro).

### C2 — Vista Hoy (datos)

- `GET /api/hoy/` devuelve `generado_en`, `total`, `filtros` y `grupos` con:
  - **vencidas**: fecha pasada, o es hoy y la hora límite ya pasó.
  - **para_hoy**: vence hoy y su hora aún no pasa.
  - **proximas**: fecha futura.
- Orden dentro de cada grupo: fecha límite → menor esfuerzo estimado → hora límite.

### C5 — API `/hoy/` documentada con filtros

- Filtros: `?evento=<id>` (solo eventos propios) y
  `?estado=abiertas|pendiente|en_progreso|hecho|todas` (por defecto `abiertas`).
- Documentada en Swagger con parámetros, ejemplos de cada filtro y un ejemplo completo de
  respuesta agrupada.
- Estructura de cada gestión: `id`, `titulo`, `categoria`, `estado`, `prioridad`, `fecha_limite`,
  `hora_limite`, `hora_inicio`, `estimacion_horas` y `evento { id, nombre }`.

---

## Evidencia técnica consolidada

- **23 tests** en `eventos/api/tests.py`:
  - `AutenticacionTests` (7): 401 sin token, registro, correo duplicado, contraseña débil,
    login válido/ inválido, `me` y `logout`.
  - `AislamientoTests` (7): listados, detalle, edición, eliminación y gestiones entre cuentas;
    el dueño se asigna desde la sesión.
  - `HoyTests` (9): agrupación por fecha y hora, orden por esfuerzo, filtros, códigos de error y
    aislamiento; con reloj fijo para resultados deterministas.
- Esquema OpenAPI validado con `manage.py spectacular --validate` (0 errores, 0 advertencias).
- Prueba de humo contra Postgres real: registro 201 → evento 201 → gestión 201 → `/api/hoy/`
  agrupado → 401 sin token → el organizador B no ve datos del A.

## Pendientes y evidencia externa

- Tablero Kanban, Documento Único y bitácora UX/HCI: se enlazan desde allí; este repo solo aporta
  la API y su documentación.
- Recuperación de contraseña por correo: no implementada (no hay servicio de email en el alcance);
  la UI avisa que lo gestione el administrador.
- Variables de entorno de producción en Render: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`,
  `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`.
