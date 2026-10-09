# Cumplimiento de criterios por Sprint — Backend

Este documento describe, para el repositorio **Backend-Eventos-PI**, todo lo que ya está
implementado y verificado en relación con los criterios de los sprints 0, 1, 2 y 3. Las ramas de
trabajo han sido `feature/sprint-auth-hoy`, `feat/backend-limites-horas` y
`feature/sprint3-capacidad-conflictos`.

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

### Análisis de responsabilidades: backend vs. frontend

| # | Requerimiento | Responsable | Justificación arquitectural |
| --- | --- | --- | --- |
| 1 | Reprogramar gestiones: cambio de plazo/fecha persiste y se refleja en `/hoy` | **Backend** | Transaccionalidad de BD y recálculo en la agrupación temporal de `/api/hoy/`. |
| 2 | Límite diario configurable de horas: set/get + default 6h por organizador | **Backend** | Modelo de datos por usuario, persistencia relacional y endpoints de configuración. |
| 3 | Conflicto estándar: detecta sobrecarga diaria al reprogramar con cifras | **Backend** | Agregación de horas del día, aborto atómico y contrato JSON HTTP 409 con métricas. |
| 4 | Resolución de conflicto: ≥1 estrategia funcional (mover día / reducir horas) | **Backend** | Endpoints de mutación controlada para aplicar la estrategia seleccionada. |
| 5 | Calidad IxD: diálogo de conflicto con opciones comprensibles sin jerga técnica | **Frontend** | Interfaz de usuario, modal interactivo y redacción UX basada en el JSON del 409. |
| 6 | Evidencia UX/HCI (prevención de errores) + endpoints documentados + bitácora | **Compartido** | Backend aporta esquemas OpenAPI, prevención de integridad y bitácora técnica; Frontend aporta bitácora UX. |

### C1 — Límite diario configurable por organizador (set/get + default 6h)

- Modelo `ConfiguracionOrganizador` con relación `OneToOneField` a `auth.User`, campo
  `limite_diario_horas` con `default=Decimal('6.00')`.
- Señal Django `post_save` (`asegurar_configuracion_organizador`): crea automáticamente la
  configuración por defecto al registrar cada usuario.
- Endpoints transaccionales:
  - `GET /api/config/`: consulta el límite actual (si no existe registro, lo inicializa en 6.00h).
  - `PUT /api/config/`: actualización total del límite con validación de rango (1 ≤ límite ≤ 16).
  - `PATCH /api/config/`: actualización parcial del límite.
- Enriquecimiento de sesión: `GET /api/auth/me/` incluye `limite_diario_horas` directamente en la
  carga útil del organizador, tipado con `@extend_schema_field`.

### C2 — Detección de sobrecarga diaria al reprogramar (HTTP 409 Conflict)

- Acción `PATCH /api/subtareas/{id}/reprogramar/` con soporte de parámetros `plazo`, `hora_limite`
  (opcional) y `estimacion_horas` (opcional).
- **Algoritmo de cálculo de sobrecarga (`_cifras_dia` / `_calcular_sobrecarga`):**
  1. Obtiene el límite configurado del organizador autenticado.
  2. Suma las estimaciones de horas de todas las gestiones **abiertas** del organizador en la fecha
     destino (excluye las marcadas como `hecho`), excluyendo la gestión actual para evitar conteo doble.
  3. Suma la nueva estimación y calcula el exceso proyectado (`proyectadas - limite`).
  4. Si `exceso > 0`, **aborta la transacción** sin alterar la base de datos y responde con
     **HTTP 409 Conflict**.
- **Fechas sugeridas (`_sugerir_fechas`):** el 409 incluye hasta 3 días próximos (horizonte de 90
  días) en los que la gestión cabe dentro del límite, para que el organizador resuelva el conflicto
  con un clic.
- Estructura JSON del conflicto estructurada para consumo directo del frontend:
  ```json
  {
    "conflicto": true,
    "codigo": "SOBRECARGA_DIARIA",
    "mensaje": "Sobrecarga detectada para el 20/10/2026. Tu límite diario es de 6.00h y con esta gestión acumularías 7.50h, superando el límite por 1.50h. Elige una estrategia para resolver el conflicto.",
    "fecha": "2026-10-20",
    "limite_horas": "6.00",
    "horas_actuales": "5.00",
    "horas_nueva_gestion": "2.50",
    "horas_totales_proyectadas": "7.50",
    "horas_exceso": "1.50",
    "estrategias_disponibles": ["mover_otro_dia", "reducir_horas"],
    "fechas_sugeridas": [
      {"fecha": "2026-10-21", "horas_totales_proyectadas": "2.50"}
    ]
  }
  ```

### C3 — Resolución de conflictos con estrategias funcionales

- Endpoint `POST /api/subtareas/{id}/resolver-conflicto/` que recibe `estrategia`:
  - **`mover_otro_dia`**: recibe `plazo` y opcionalmente `hora_limite`; aplica el nuevo plazo atómicamente.
  - **`reducir_horas`**: recibe `estimacion_horas`; reduce la duración estimada manteniendo la fecha.
- **Recálculo posterior:** tras aplicar la estrategia, el servidor recalcula el día destino y responde
  `resuelto: true/false` junto con `limite_horas`, `horas_totales_proyectadas`, `horas_exceso` y, si el
  conflicto persiste, nuevas `fechas_sugeridas`. Así el frontend puede confirmar que el plan quedó
  viable o informar que el exceso continúa.
- Validación de parámetros obligatorios según la estrategia elegida (responde 400 con mensaje claro
  si faltan campos requeridos).
- Aislamiento estricto: responde 404 si la gestión pertenece a otro organizador.

### C4 — Persistencia y reflejo en `/hoy/`

- Al reprogramar exitosamente sin conflicto (o tras resolverlo), la actualización persiste en
  PostgreSQL / SQLite de manera atómica (`transaction.atomic`).
- La vista `/api/hoy/` reagrupa inmediatamente la gestión en `vencidas`, `para_hoy` o `proximas` de
  acuerdo con el nuevo plazo y hora límite.

### C5 — Validaciones backend y prevención de errores

| Regla | Código HTTP | Mensaje / Estructura |
| --- | --- | --- |
| Límite diario fuera del rango 1–16 | 400 Bad Request | "El límite diario debe estar entre 1 y 16 horas." |
| Estimación de horas menor o igual a 0 | 400 Bad Request | "La estimación debe ser mayor a 0 horas." |
| Sobrecarga diaria al reprogramar | 409 Conflict | JSON estructurado con `codigo: SOBRECARGA_DIARIA`, métricas del exceso, `estrategias_disponibles` y `fechas_sugeridas`. |
| Estrategia `mover_otro_dia` sin plazo | 400 Bad Request | "Se requiere 'plazo' para la estrategia 'mover_otro_dia'." |
| Estrategia `reducir_horas` sin estimación | 400 Bad Request | "Se requiere 'estimacion_horas' para la estrategia 'reducir_horas'." |
| Operación en gestión ajena | 404 Not Found | "Gestión no encontrada o no te pertenece." |
| Solicitud sin autenticación | 401 Unauthorized | "Las credenciales de autenticación no se proveyeron." |

### C6 — Bitácora de archivos intervenidos

Detalle de cada uno de los archivos modificados en el repositorio:

1. **`eventos/api/models.py`**:
   - Creación del modelo `ConfiguracionOrganizador` con `usuario` (`OneToOneField` a `User`),
     `limite_diario_horas` (`DecimalField(max_digits=4, decimal_places=2, default=6.00)`), marcas
     temporales `creado_en` y `actualizado_en`.
   - Incorporación de la señal `asegurar_configuracion_organizador` (`post_save`).
2. **`eventos/api/admin.py`**:
   - Registro de `ConfiguracionOrganizador` con listado de campos `usuario`, `limite_diario_horas`,
     `actualizado_en` y búsqueda por nombre de usuario y correo.
3. **`eventos/api/migrations/0007_configuracion_organizador.py`**:
   - Migración Django versionada que crea la tabla `api_configuracionorganizador` compatible con
     PostgreSQL (Supabase/Render) y SQLite local.
4. **`eventos/api/serializers.py`**:
   - Serializadores creados: `ConfiguracionOrganizadorSerializer`, `ReprogramarTareaSerializer`,
     `ResolverConflictoSerializer`, `FechaSugeridaSerializer`, `DetalleConflictoSerializer`,
     `ErrorConflictoSerializer` y `ResolverConflictoRespuestaSerializer`.
   - Validación de rango del límite diario entre 1 y 16 horas.
   - Modificación de `UsuarioSerializer` para exponer `limite_diario_horas` con anotación
     `@extend_schema_field(serializers.CharField())` para OpenAPI.
5. **`eventos/api/views.py`**:
   - Implementación de `ConfiguracionOrganizadorView` (GET, PUT, PATCH).
   - Implementación de los helpers `_obtener_limite_organizador`, `_cifras_dia`, `_calcular_sobrecarga`
     (excluye gestiones hechas) y `_sugerir_fechas` (hasta 3 días viables en 90 días).
   - Adición de la acción `reprogramar` en `SubtareaViewSet` con retorno HTTP 409 y atomicidad.
   - Creación de `ResolverConflictoView` que aplica la estrategia y **recalcula** el día destino,
     respondiendo `resuelto`, totales y nuevas sugerencias.
   - Documentación exhaustiva con decoradores `@extend_schema`, esquemas de respuesta 200/400/409 y
     ejemplos representativos.
6. **`eventos/api/urls.py`**:
   - Registro de ruta `api/config/` para la configuración del organizador.
   - Registro de ruta `api/subtareas/<pk>/resolver-conflicto/`.
   - El router registra automáticamente la acción `api/subtareas/<pk>/reprogramar/`.
7. **`eventos/api/tests.py`**:
   - 27 tests en 3 suites: `ConfiguracionTests` (11), `ReprogramarTests` (8) y
     `ResolverConflictoTests` (8).
8. **`eventos/eventos/settings.py`**:
   - Actualización de `SPECTACULAR_SETTINGS['TAGS']` con la etiqueta y descripción del módulo
     `configuracion`.
9. **`CUMPLIMIENTO-SPRINTS.md`**:
   - Bitácora y seguimiento técnico de los criterios del Sprint 3.
10. **`README.md`**:
    - Actualización de la tabla de endpoints principales de la API.

### Nuevas rutas agregadas

| Método | Ruta | Auth | Descripción |
| --- | --- | --- | --- |
| GET | `/api/config/` | Token | Consulta el límite diario de horas de gestión (default 6.00h). |
| PUT/PATCH | `/api/config/` | Token | Actualiza total o parcialmente el límite diario de horas. |
| PATCH | `/api/subtareas/{id}/reprogramar/` | Token | Reprograma una gestión evaluando sobrecarga; responde 409 si supera el límite. |
| POST | `/api/subtareas/{id}/resolver-conflicto/` | Token | Aplica estrategia de resolución (`mover_otro_dia` o `reducir_horas`). |

---

## Evidencia técnica consolidada

- **50 tests** en `eventos/api/tests.py` (todos ejecutándose con éxito en SQLite local):
  - `AutenticacionTests` (8): 401 sin token, registro, correo duplicado, contraseña débil,
    login válido/inválido, `me` y `logout`.
  - `AislamientoTests` (7): listados, detalle, edición, eliminación y gestiones entre cuentas;
    el dueño se asigna desde la sesión.
  - `HoyTests` (8): agrupación por fecha y hora, orden por esfuerzo, filtros, códigos de error y
    aislamiento; con reloj fijo para resultados deterministas.
  - `ConfiguracionTests` (11): GET del límite por defecto (6h), PUT/PATCH de actualización,
    rango 1–16 (rechaza 0.5 y 17, acepta 1 y 16), independencia por organizador, token requerido
    y exposición en `/api/auth/me/`.
  - `ReprogramarTests` (8): reprogramación exitosa sin sobrecarga (200), detección de sobrecarga
    con cifras exactas (409), no mutación de la BD tras aborto 409, reducción de horas que evita
    sobrecarga, `fechas_sugeridas` válidas dentro del límite, las gestiones hechas no suman en la
    carga del día, token requerido y protección contra gestiones ajenas (404).
  - `ResolverConflictoTests` (8): estrategia `mover_otro_dia`, estrategia `reducir_horas`,
    reducción que aún excede (resuelto false + nuevas sugerencias), movimiento a un día cargado
    que persiste y reporta el conflicto, validación de campos obligatorios (400), protección
    contra gestiones ajenas (404) y token requerido (401).
- Esquema OpenAPI validado con `manage.py spectacular --validate` (**0 errores, 0 advertencias**).
- Migración `api/migrations/0007_configuracion_organizador.py` aplicada y verificada.

## Pendientes y evidencia externa

- Tablero Kanban, Documento Único y bitácora UX/HCI: se enlazan desde allí; este repo aporta
  la API, las validaciones transaccionales y la documentación OpenAPI.
- Recuperación de contraseña por correo: no implementada (no hay servicio de email en el alcance);
  la UI avisa que lo gestione el administrador.
- Variables de entorno de producción en Render: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`,
  `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`.


