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

## Sprint 3 — Reprogramación, sobrecarga y resolución de conflictos

### Análisis de requerimientos: backend vs. frontend

| # | Requerimiento | Responsable |
| --- | --- | --- |
| 1 | Reprogramar gestión (cambio de plazo/fecha persiste y se refleja en `/hoy`) | **Backend** — PATCH + lógica de sobrecarga |
| 2 | Límite diario configurable de horas por organizador (set/get, default 6h) | **Backend** — modelo + endpoints |
| 3 | Conflicto estándar: detección de sobrecarga con cifras exactas | **Backend** — validación atómica → 409 JSON |
| 4 | Resolución: ≥1 estrategia funcional (mover día / reducir horas) | **Backend** — endpoint `resolver-conflicto` |
| 5 | Calidad IxD: diálogo de conflicto sin jerga técnica | **Frontend** — consume el JSON del 409 |
| 6 | Evidencia UX/HCI + endpoints documentados + bitácora | **Backend** (docs) + **Frontend** (UX) |

### C1 — Límite diario configurable

- Nuevo modelo `ConfiguracionOrganizador` (OneToOne a `auth.User`, `default=6.00`), migración
  `0007_configuracion_organizador`.
- Se crea automáticamente (señal `post_save`) al registrar un organizador.
- Endpoints:
  - `GET /api/config/` — devuelve `{ "limite_diario_horas": "6.00" }`.
  - `PUT /api/config/` — actualiza el límite (validación: > 0 y ≤ 24).
  - `PATCH /api/config/` — actualización parcial.
- `GET /api/auth/me/` ahora incluye `limite_diario_horas` del organizador autenticado.

### C2 — Reprogramar con detección de sobrecarga (409 Conflict)

- `PATCH /api/subtareas/{id}/reprogramar/` acepta `plazo`, `hora_limite` (opcional) y
  `estimacion_horas` (opcional).
- **Algoritmo:** suma `estimacion_horas` de todas las subtareas del organizador cuyo `plazo` sea la
  nueva fecha (excluyendo la propia), compara con el límite. Si el exceso > 0 → **aborta** (sin
  escribir en BD) y devuelve `409` con:
  ```json
  {
    "conflicto": true,
    "codigo": "SOBRECARGA_DIARIA",
    "mensaje": "Sobrecarga detectada para el 20/10/2026. Tu límite diario es de 6.00h…",
    "fecha": "2026-10-20",
    "limite_horas": "6.00",
    "horas_actuales": "5.00",
    "horas_nueva_gestion": "2.50",
    "horas_totales_proyectadas": "7.50",
    "horas_exceso": "1.50",
    "estrategias_disponibles": ["mover_otro_dia", "reducir_horas"]
  }
  ```
- Sin conflicto → persiste atómicamente y devuelve `200` con la gestión actualizada.
- El cambio persiste en `/api/hoy/` inmediatamente (agrupa por `plazo`).

### C3 — Resolución de conflicto

- `POST /api/subtareas/{id}/resolver-conflicto/` con campo `estrategia`:
  - `mover_otro_dia` + `plazo` (requerido) → mueve sin re-validar.
  - `reducir_horas` + `estimacion_horas` (requerido) → ajusta la estimación; mantiene el plazo.
- Ambas estrategias persisten atómicamente y devuelven la gestión actualizada.

### Nuevas rutas (tabla actualizada)

| Método | Ruta | Auth | Descripción |
| --- | --- | --- | --- |
| GET/PUT/PATCH | `/api/config/` | Token | Límite diario de horas del organizador. |
| PATCH | `/api/subtareas/{id}/reprogramar/` | Token | Reprogramar con detección de sobrecarga (409). |
| POST | `/api/subtareas/{id}/resolver-conflicto/` | Token | Aplicar estrategia de resolución. |

---

## Evidencia técnica consolidada

- **48 tests** en `eventos/api/tests.py`:
  - `AutenticacionTests` (7): 401 sin token, registro, correo duplicado, contraseña débil,
    login válido/inválido, `me` y `logout`.
  - `AislamientoTests` (7): listados, detalle, edición, eliminación y gestiones entre cuentas;
    el dueño se asigna desde la sesión.
  - `HoyTests` (9): agrupación por fecha y hora, orden por esfuerzo, filtros, códigos de error y
    aislamiento; con reloj fijo para resultados deterministas.
  - `ConfiguracionTests` (8): GET/PUT/PATCH del límite, validaciones (0, negativo, > 24h),
    token requerido, `me` expone el límite.
  - `ReprogramarTests` (6): sin conflicto → 200, con sobrecarga → 409 con cifras, no modifica BD
    en conflicto, reducción evita sobrecarga, token requerido, aislamiento entre organizadores.
  - `ResolverConflictoTests` (6): estrategia mover día, reducir horas, 400 sin campos requeridos,
    404 en gestión ajena, token requerido.
- Esquema OpenAPI validado con `manage.py spectacular --validate` (**0 errores, 0 advertencias**).
- Migración `0007_configuracion_organizador` incluida.

## Pendientes y evidencia externa

- Tablero Kanban, Documento Único y bitácora UX/HCI: se enlazan desde allí; este repo solo aporta
  la API y su documentación.
- Recuperación de contraseña por correo: no implementada (no hay servicio de email en el alcance);
  la UI avisa que lo gestione el administrador.
- Variables de entorno de producción en Render: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`,
  `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`.

