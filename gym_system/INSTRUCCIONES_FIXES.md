# Archivos corregidos — gym_system

Reemplaza cada archivo en tu proyecto con el correspondiente de esta carpeta.

## Mapa de archivos

```
INSTRUCCIONES_FIXES.md          ← este archivo
config.py                       → gym_system/config.py
render.yaml                     → gym_system/render.yaml
services/expiry_job.py          → gym_system/services/expiry_job.py
services/backup_service.py      → gym_system/services/backup_service.py
routes/attendance_routes.py     → gym_system/routes/attendance_routes.py
routes/inventory_routes.py      → gym_system/routes/inventory_routes.py
routes/notification_routes.py   → gym_system/routes/notification_routes.py
routes/reports_routes.py        → gym_system/routes/reports_routes.py
routes/settings_routes.py       → gym_system/routes/settings_routes.py
```

---

## Qué se cambió y por qué

### 1. `config.py` — Credenciales removidas
- Se eliminó la URL de Neon con usuario/contraseña del código.
- Ahora el app lanza un `RuntimeError` si `DATABASE_URL` no está definida
  como variable de entorno, en lugar de conectarse con credenciales expuestas.

### 2. `render.yaml` — Credenciales removidas
- Se eliminó la `DATABASE_URL` hardcodeada.
- Se reemplazó con `sync: false`, que le dice a Render que el valor
  se configura manualmente en el dashboard (Environment → Add Secret).

**Acción requerida en Render:**
  1. Dashboard → tu servicio → Environment
  2. Add Secret File o Add Environment Variable
  3. Key: `DATABASE_URL`
  4. Value: tu URL de Neon (la misma que estaba antes en el código)

### 3. `services/expiry_job.py` — Job de vencimientos arreglado
- Antes: el control "ya corrió hoy" tenía un `pass` — nunca guardaba la fecha,
  por lo que corría cada 5 minutos y enviaba emails repetidos.
- Ahora: guarda la fecha en memoria (para el proceso actual) y también en
  `GymSettings.notes` (persiste entre reinicios del servidor).

### 4. `services/backup_service.py` — Backup sin pg_dump
- Antes: usaba `subprocess` con `pg_dump`, que no existe en Render free.
  El botón "Crear Respaldo" siempre fallaba en producción.
- Ahora: exporta todas las tablas a JSON usando SQLAlchemy directamente.
  Funciona en cualquier entorno sin dependencias externas.
  Los backups se guardan como `backup_YYYYMMDD_HHMMSS.json` en `/backups/`.

### 5. Routes unificados — Autenticación con decorador
Los siguientes routes usaban `if 'user_id' not in session` manualmente.
Se reemplazaron por `@login_required` (y `@role_required` donde aplica):

- `attendance_routes.py`
- `inventory_routes.py` → create/edit/delete ahora requieren rol `admin`
- `notification_routes.py`
- `reports_routes.py`
- `settings_routes.py` → ahora requiere rol `admin`
