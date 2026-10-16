# 🚀 Despliegue en Render (gratis) — Base de datos Neon ya configurada

## ✅ La base de datos Neon ya está integrada en el proyecto

La conexión a Neon está configurada directamente en `config.py` y `render.yaml`.
**No necesitas crear ni configurar la base de datos** — ya está lista.

---

## PASO 1 — Subir a GitHub

Si aún no lo has hecho, crea un repositorio en https://github.com y sube el código:

```bash
git add .
git commit -m "Neon DB configurada"
git push
```

Si es la primera vez:
```bash
git init
git add .
git commit -m "GymSystem con Neon DB"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/gymsystem.git
git push -u origin main
```

---

## PASO 2 — Crear el Web Service en Render

1. Ve a https://render.com → **"New +"** → **"Web Service"**
2. Conecta el repositorio `gymsystem`
3. Configura:

| Campo | Valor |
|---|---|
| Name | `gymsystem` |
| Region | `Ohio (US East)` |
| Branch | `main` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:application --workers 1 --threads 4 --worker-class gthread --timeout 120 --bind 0.0.0.0:$PORT` |
| Plan | **Free** |

4. En **"Environment Variables"** agrega **solo esto**:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | Genera uno en https://randomkeygen.com (Fort Knox) |
| `FLASK_ENV` | `production` |

> La `DATABASE_URL` de Neon ya viene incluida en `render.yaml` — no la necesitas agregar manualmente.

5. Clic **"Create Web Service"** → espera ~3 minutos hasta ver **"Live"** ✅

---

## PASO 3 — Inicializar la base de datos (solo la primera vez)

1. Web Service → pestaña **"Shell"**
2. Ejecuta:
```bash
python seed.py
```

Verás:
```
✅ Base de datos inicializada.
👤 Usuario: admin | Contraseña: Admin2025!
```

---

## PASO 4 — Entrar al sistema

URL: `https://gymsystem.onrender.com`

- **Usuario:** `admin`
- **Contraseña:** `Admin2025!`
- ⚠️ Cambia la contraseña inmediatamente

---

## PASO 5 — Eliminar el cold start con UptimeRobot (gratis)

Render gratuito duerme el servidor tras 15 min de inactividad (cold start de ~20s).
UptimeRobot lo pinga cada 5 min para mantenerlo activo siempre.

1. Ve a https://uptimerobot.com → **"Register for FREE"**
2. **"Add New Monitor"**:
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `GymSystem`
   - URL: `https://gymsystem.onrender.com/health`
   - Interval: `5 minutes`
3. **"Create Monitor"** ✅

---

## PASO 6 — Actualizaciones futuras

```bash
git add .
git commit -m "descripción del cambio"
git push
```
Render redespliega automáticamente.

---

## 🔧 Problemas comunes

**Error de SSL con Neon**
→ Ya configurado en `config.py` con `sslmode=require` y `channel_binding=require`

**"too many connections" en Neon**
→ Neon free permite 10 conexiones. Ya configurado con `pool_size=3`. Si persiste, en Neon dashboard activa **Connection Pooling** y usa la URL con puerto 6543.

**"no such table"**
→ Ejecuta `python seed.py` desde la Shell de Render

**La app no carga (timeout)**
→ Configura UptimeRobot (Paso 5)

## Asistente IA (opcional)
Variables de entorno en Render:
- `AI_API_KEY`  → tu llave (Gemini, Groq, OpenRouter u OpenAI)
- `AI_BASE_URL` → por defecto Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`
  (Groq: `https://api.groq.com/openai/v1`)
- `AI_MODEL`    → por defecto `gemini-2.0-flash` (Groq: `llama-3.3-70b-versatile`)
