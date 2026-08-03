import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from supabase import create_client, Client

app = Flask(__name__)

# === CONFIGURACIÓN DE SESIÓN Y SEGURIDAD ===
app.secret_key = "mudream_master_secret_key_2026_super_segura_fixed"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# === CONEXIÓN A SUPABASE ===
# Tip: Te recomendamos mover estas claves a variables de entorno por seguridad
SUPABASE_URL = "https://sfdoobkwnaljgrmbzwvl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNmZG9vYmt3bmFsamdybWJ6d3ZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NDgzMjcsImV4cCI6MjEwMTMyNDMyN30.ZvkJqP9QiDFAi9syxeMnam6gOlVMTMhiD_wEudqt11I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

COOLDOWNS = {
    "Muggron 1": 180,
    "Muggron 2": 180,
    "Muggron Barracks 1": 180,
    "Muggron Barracks 2": 180,
    "Muggron Crywolf 1": 180,
    "Muggron Crywolf 2": 180,
    "Kharzul": 420, 
    "Vescrya": 420,
    "Borgar": 120, 
    "Dreadhorn": 60,
    "Yellow Goblin": 600,
    "Blue Goblin": 600,
    "Red Goblin": 600,
    "Red Dragon": 720
}

SERVIDORES = ["Server 1", "Server 2", "Server 3", "Server 20"]

# === FUNCIONES AUXILIARES ===
def parsear_fecha_utc(dt_str):
    """
    Convierte cualquier cadena ISO de Supabase a un objeto datetime UTC nativo.
     Evita el crash por incompatibilidad de Timezones.
    """
    if not dt_str:
        return None
    try:
        clean_str = str(dt_str).replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(clean_str)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj
    except Exception as e:
        print(f"⚠️ Error parseando fecha '{dt_str}': {e}")
        return None

# === FUNCIONES DE BASE DE DATOS ===
def validar_usuario(username, password):
    try:
        usr_clean = username.strip() if username else ""
        pwd_clean = password.strip() if password else ""

        print(f"🔍 Intentando validar usuario: '{usr_clean}'")
        res = supabase.table('usuarios').select('*').eq('username', usr_clean).eq('password', pwd_clean).execute()
        
        if res.data and len(res.data) > 0:
            user = res.data[0]
            if user.get('activo', False):
                print(f"✅ Usuario valido y activo: {user['username']} (Rol: {user.get('role')})")
                return user
            else:
                print(f"⚠️ Usuario encontrado pero está INACTIVO: {usr_clean}")
        else:
            print(f"❌ Usuario o contraseña incorrectos en Supabase para: '{usr_clean}'")
    except Exception as e:
        print(f"❌ Error grave validando usuario en Supabase: {e}")
    return None

def obtener_datos_nube():
    # Estructuras por defecto seguras
    timers_map = {svr: {} for svr in SERVIDORES}
    pcs_map = {svr: "Sin reportes" for svr in SERVIDORES}
    pj_map = {svr: "Desconocido" for svr in SERVIDORES}
    heartbeat_map = {svr: None for svr in SERVIDORES}

    try:
        res = supabase.table('timers_bosses').select('*').execute()
        ahora_utc = datetime.now(timezone.utc)

        if res.data:
            for row in res.data:
                svr = row.get('server')
                if not svr or svr not in SERVIDORES:
                    continue

                boss_timers = {}
                raw_timers = row.get('timers') or {}

                if isinstance(raw_timers, dict):
                    for boss, dt_str in raw_timers.items():
                        dt_obj = parsear_fecha_utc(dt_str)
                        if dt_obj and dt_obj > ahora_utc:
                            boss_timers[boss] = int(dt_obj.timestamp())

                timers_map[svr] = boss_timers
                pcs_map[svr] = row.get('last_pc') or 'Sin reportes'
                pj_map[svr] = row.get('last_pj') or 'Desconocido'
                heartbeat_map[svr] = row.get('last_heartbeat')

        return timers_map, pcs_map, pj_map, heartbeat_map
    except Exception as e:
        print(f"❌ Error leyendo Supabase en obtener_datos_nube: {e}")
        return timers_map, pcs_map, pj_map, heartbeat_map

def guardar_boss_nube(server, boss, pc_id, pj_name):
    try:
        res = supabase.table('timers_bosses').select('timers').eq('server', server).execute()
        current_timers = (res.data[0]['timers'] if res.data and res.data[0].get('timers') else {})
        
        # Fecha en UTC
        nueva_fecha = datetime.now(timezone.utc) + timedelta(minutes=COOLDOWNS[boss])
        current_timers[boss] = nueva_fecha.isoformat()

        supabase.table('timers_bosses').update({
            'timers': current_timers,
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': datetime.now(timezone.utc).isoformat()
        }).eq('server', server).execute()
    except Exception as e:
        print(f"❌ Error guardando en Supabase: {e}")

def actualizar_heartbeat_nube(server, pc_id, pj_name):
    try:
        supabase.table('timers_bosses').update({
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': datetime.now(timezone.utc).isoformat()
        }).eq('server', server).execute()
    except Exception as e:
        print(f"❌ Error heartbeat: {e}")

def borrar_boss_nube(server, boss):
    try:
        res = supabase.table('timers_bosses').select('timers').eq('server', server).execute()
        current_timers = (res.data[0]['timers'] if res.data and res.data[0].get('timers') else {})
        if boss in current_timers:
            del current_timers[boss]
            supabase.table('timers_bosses').update({'timers': current_timers}).eq('server', server).execute()
    except Exception as e:
        print(f"❌ Error reseteando en Supabase: {e}")

# === PLANTILLAS HTML ===
HTML_LOGIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>🔐 Acceso - Monitor MuDream</title>
    <style>
        body { background: #0a0814; color: #fff; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #141126; border: 1px solid #2a244d; border-radius: 12px; padding: 30px; width: 340px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { margin-top: 0; color: #9d4edd; }
        input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 6px; border: 1px solid #2a244d; background: #0a0814; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 10px; border-radius: 6px; border: none; background: #7b2cbf; color: white; font-weight: bold; cursor: pointer; margin-top: 10px; }
        button:hover { background: #9d4edd; }
        .error { color: #ff4757; font-size: 0.85rem; margin-top: 10px; font-weight: bold; }
        .success { color: #2ecc71; font-size: 0.85rem; margin-top: 10px; }
        .link-btn { display: inline-block; margin-top: 15px; color: #8e85b8; font-size: 0.85rem; text-decoration: none; }
        .link-btn:hover { color: #fff; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚔️ MUDREAM LOGIN ⚔️</h2>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="Usuario" required>
            <input type="password" name="password" placeholder="Contraseña" required>
            <button type="submit">Ingresar</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if msg %}<div class="success">{{ msg }}</div>{% endif %}
        <a href="/register" class="link-btn">¿No tenés cuenta? Registrate acá</a>
    </div>
</body>
</html>
"""

HTML_REGISTER = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>📝 Registro - Monitor MuDream</title>
    <style>
        body { background: #0a0814; color: #fff; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #141126; border: 1px solid #2a244d; border-radius: 12px; padding: 30px; width: 340px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { margin-top: 0; color: #9d4edd; }
        input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 6px; border: 1px solid #2a244d; background: #0a0814; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 10px; border-radius: 6px; border: none; background: #7b2cbf; color: white; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .error { color: #ff4757; font-size: 0.85rem; margin-top: 10px; }
        .link-btn { display: inline-block; margin-top: 15px; color: #8e85b8; font-size: 0.85rem; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📝 CREAR CUENTA</h2>
        <form method="POST" action="/register">
            <input type="text" name="username" placeholder="Usuario deseado" required>
            <input type="password" name="password" placeholder="Contraseña" required>
            <button type="submit">Solicitar Registro</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <a href="/login" class="link-btn">⬅️ Volver al Login</a>
    </div>
</body>
</html>
"""

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Monitor Multi-PC - MuDream ⚔️</title>
    <style>
        :root { --bg-dark: #0a0814; --card-bg: #141126; --card-border: #2a244d; --accent-purple: #7b2cbf; --accent-glow: #9d4edd; --text-primary: #e6e1ff; --text-secondary: #8e85b8; --alive-green: #2ecc71; --cd-red: #ff4757; --window-yellow: #f1c40f; }
        body { font-family: 'Segoe UI', sans-serif; background-color: var(--bg-dark); color: var(--text-primary); margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        header { text-align: center; margin-bottom: 20px; width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; }
        h1 { font-size: 1.8rem; margin: 0; color: #fff; text-shadow: 0 0 10px rgba(123, 44, 191, 0.5); }
        .top-links { display: flex; gap: 10px; align-items: center; }
        .top-links a { color: var(--accent-glow); text-decoration: none; font-weight: bold; font-size: 0.9rem; padding: 6px 12px; background: #141126; border-radius: 6px; border: 1px solid var(--card-border); }
        .controls-bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-bottom: 25px; background: #100d21; padding: 12px 20px; border-radius: 12px; border: 1px solid var(--card-border); }
        .view-btn { background: #1e1938; border: 1px solid var(--card-border); color: var(--text-primary); padding: 10px 18px; font-size: 0.95rem; font-weight: 600; border-radius: 8px; cursor: pointer; }
        .view-btn.active { background: var(--accent-purple); border-color: var(--accent-glow); color: #fff; }
        .dashboard-container { width: 100%; max-width: 1200px; }
        .grid-all { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }
        .server-block { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; }
        .server-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--card-border); padding-bottom: 10px; margin-bottom: 8px; }
        .server-title { font-size: 1.4rem; font-weight: bold; color: #fff; }
        .bot-status-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 0.8rem; background: #0c091f; padding: 6px 10px; border-radius: 6px; }
        .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
        .dot-online { background-color: var(--alive-green); }
        .dot-offline { background-color: var(--cd-red); }
        .pc-badge { font-size: 0.75rem; color: var(--text-secondary); }
        .pj-badge { font-size: 0.8rem; color: #b8acff; font-weight: bold; }
        .boss-list { display: flex; flex-direction: column; gap: 10px; }
        .boss-row { background: #0d0a1a; border: 1px solid #1f1a3a; border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; }
        .boss-name { font-weight: bold; font-size: 0.95rem; }
        .boss-respawn { font-size: 0.75rem; color: var(--text-secondary); }
        .timer-badge { font-family: monospace; font-size: 1rem; font-weight: bold; padding: 4px 8px; border-radius: 6px; text-align: center; min-width: 110px; }
        .status-alive { color: var(--alive-green); border: 1px solid var(--alive-green); }
        .status-cd { color: var(--cd-red); border: 1px solid var(--cd-red); }
        .status-window { color: var(--window-yellow); border: 1px solid var(--window-yellow); }
        .btn-action { background: var(--accent-purple); border: none; color: white; padding: 6px 10px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.85rem; }
        .btn-reset { background: #2a2347; color: #aaa; margin-left: 4px; }
    </style>
</head>
<body>

    <header>
        <h1>⚔️ MONITOR MUDREAM ⚔️</h1>
        <div class="top-links">
            {% if session.get('role') == 'admin' %}
                <a href="/admin" style="border-color:#9d4edd; background:#7b2cbf; color:#fff;">⚙️ Panel Admin</a>
            {% endif %}
            <a href="/logout">🚪 Cerrar Sesión ({{ session.get('user') }})</a>
        </div>
    </header>

    <div class="controls-bar">
        <button class="view-btn active" onclick="setVista('TODOS')">👁️ Ver Todos Juntos</button>
        <button class="view-btn" onclick="setVista('Server 1')">Server 1</button>
        <button class="view-btn" onclick="setVista('Server 2')">Server 2</button>
        <button class="view-btn" onclick="setVista('Server 3')">Server 3</button>
        <button class="view-btn" onclick="setVista('Server 20')">Server 20</button>
    </div>

    <div class="dashboard-container" id="dashboard"></div>

    <script>
        let modoVista = 'TODOS';
        let estadoWeb = {};

        function setVista(vista) {
            modoVista = vista;
            document.querySelectorAll('.view-btn').forEach(btn => {
                const esActivo = (vista === 'TODOS' && btn.innerText.includes('Todos')) || btn.innerText === vista;
                btn.classList.toggle('active', esActivo);
            });
            render();
        }

        async function pedirTimers() {
            try {
                const res = await fetch('/api/timers');
                if (res.status === 401) { window.location.href = '/login'; return; }
                estadoWeb = await res.json();
                render();
            } catch (e) { console.error(e); }
        }

        async function enviarAccion(endpoint, server, boss) {
            try {
                await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server, boss, pc_id: "Navegador Web", pj_name: "Web" })
                });
                pedirTimers();
            } catch (e) { console.error(e); }
        }

        function render() {
            const container = document.getElementById('dashboard');
            container.innerHTML = '';
            const serversDisponibles = estadoWeb.servers || ["Server 1", "Server 2", "Server 3", "Server 20"];
            const timers = estadoWeb.timers || {};
            const cooldowns = estadoWeb.cooldowns || {};
            const ultimosReportes = estadoWeb.ultimas_pcs || {};
            const ultimosPjs = estadoWeb.ultimos_pjs || {};
            const heartbeats = estadoWeb.heartbeats || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);
            const servidoresAMostrar = (modoVista === 'TODOS') ? serversDisponibles : [modoVista];
            container.className = (modoVista === 'TODOS') ? "dashboard-container grid-all" : "dashboard-container";

            servidoresAMostrar.forEach(svr => {
                let serverBlock = document.createElement('div');
                serverBlock.className = 'server-block';
                const pcOrigen = ultimosReportes[svr] || 'Sin reportes';
                const pjOrigen = ultimosPjs[svr] || 'Desconocido';
                let esOnline = false;
                if (heartbeats[svr]) {
                    const hbUnix = Math.floor(new Date(heartbeats[svr]).getTime() / 1000);
                    if ((ahoraUnix - hbUnix) <= 30) { esOnline = true; }
                }
                const statusHtml = esOnline 
                    ? `<span><span class="status-dot dot-online"></span><strong style="color:#2ecc71;">ONLINE</strong></span>`
                    : `<span><span class="status-dot dot-offline"></span><strong style="color:#ff4757;">OFFLINE</strong></span>`;

                let htmlContent = `
                    <div class="server-header">
                        <div class="server-title">${svr}</div>
                        <div>${statusHtml}</div>
                    </div>
                    <div class="bot-status-container">
                        <div class="pj-badge">👤 PJ: ${pjOrigen}</div>
                        <div class="pc-badge">💻 PC: ${pcOrigen}</div>
                    </div>
                    <div class="boss-list">
                `;

                const bossesServidor = timers[svr] || {};
                for (const [bossName, cdMinutos] of Object.entries(cooldowns)) {
                    if (svr === "Server 20") {
                        if (["Yellow Goblin", "Blue Goblin", "Red Goblin", "Red Dragon", "Dreadhorn", "Muggron 1", "Muggron 2"].includes(bossName)) continue;
                    } else {
                        if (["Muggron Barracks 1", "Muggron Barracks 2", "Muggron Crywolf 1", "Muggron Crywolf 2"].includes(bossName)) continue;
                    }

                    let statusState = 'alive';
                    let displayTimer = '';

                    if (bossName in bossesServidor) {
                        const targetUnix = bossesServidor[bossName];
                        const diffSec = targetUnix - ahoraUnix;
                        if (["Yellow Goblin", "Blue Goblin", "Red Goblin"].includes(bossName)) {
                            const inicioVentanaUnix = targetUnix;
                            const finVentanaUnix = targetUnix + 3600;
                            if (ahoraUnix < inicioVentanaUnix) {
                                statusState = 'cd';
                                const cdSec = inicioVentanaUnix - ahoraUnix;
                                const h = Math.floor(cdSec / 3600), m = Math.floor((cdSec % 3600) / 60), s = cdSec % 60;
                                displayTimer = `<div class="timer-badge status-cd">🔴 ${h}h ${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                            } else if (ahoraUnix >= inicioVentanaUnix && ahoraUnix <= finVentanaUnix) {
                                statusState = 'window';
                                const winSec = finVentanaUnix - ahoraUnix;
                                const m = Math.floor(winSec / 60), s = winSec % 60;
                                displayTimer = `<div class="timer-badge status-window">🟡 VENTANA (${m}m ${s < 10 ? '0':''}${s}s)</div>`;
                            }
                        } else if (diffSec > 0) {
                            statusState = 'cd';
                            const h = Math.floor(diffSec / 3600), m = Math.floor((diffSec % 3600) / 60), s = diffSec % 60;
                            displayTimer = `<div class="timer-badge status-cd">🔴 ${h > 0 ? h + 'h ' : ''}${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                        }
                    }

                    if (statusState === 'alive') displayTimer = `<div class="timer-badge status-alive">🟢 ¡VIVO!</div>`;

                    htmlContent += `
                        <div class="boss-row">
                            <div>
                                <div class="boss-name">${bossName}</div>
                                <div class="boss-respawn">${cdMinutos} min</div>
                            </div>
                            ${displayTimer}
                            <div>
                                <button class="btn-action" onclick="enviarAccion('kill', '${svr}', '${bossName}')">⚔️ Kill</button>
                                ${statusState !== 'alive' ? `<button class="btn-action btn-reset" onclick="enviarAccion('reset', '${svr}', '${bossName}')">✖</button>` : ''}
                            </div>
                        </div>
                    `;
                }
                htmlContent += `</div>`;
                serverBlock.innerHTML = htmlContent;
                container.appendChild(serverBlock);
            });
        }
        setInterval(pedirTimers, 1000);
        pedirTimers();
    </script>
</body>
</html>
"""

HTML_ADMIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>⚙️ Panel Admin - Usuarios</title>
    <style>
        body { background: #0a0814; color: #fff; font-family: sans-serif; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .box { background: #141126; border: 1px solid #2a244d; border-radius: 12px; padding: 25px; width: 100%; max-width: 650px; }
        h2 { margin-top: 0; color: #9d4edd; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; border-bottom: 1px solid #2a244d; text-align: left; }
        input, select { padding: 8px; background: #0a0814; border: 1px solid #2a244d; color: white; border-radius: 6px; }
        button { padding: 8px 14px; border: none; color: white; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .btn-toggle { background: #e74c3c; }
        .btn-active { background: #2ecc71; }
        .btn-crear { background: #7b2cbf; }
        a { color: #9d4edd; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="box">
        <a href="/">⬅️ Volver al Monitor</a>
        <h2>⚙️ Gestión de Usuarios (ADMIN)</h2>
        <form method="POST" action="/admin/crear">
            <input type="text" name="username" placeholder="Nuevo Usuario" required>
            <input type="text" name="password" placeholder="Contraseña" required>
            <button type="submit" class="btn-crear">Crear Usuario</button>
        </form>
        <table>
            <tr><th>Usuario</th><th>Contraseña</th><th>Rol</th><th>Estado</th><th>Acción</th></tr>
            {% for u in usuarios %}
            <tr>
                <td>{{ u.username }}</td>
                <td>{{ u.password }}</td>
                <td><strong style="color:{% if u.role == 'admin' %}#9d4edd{% else %}#aaa{% endif %};">{{ u.role }}</strong></td>
                <td>{% if u.activo %}<span style="color:#2ecc71;">Activo</span>{% else %}<span style="color:#e74c3c;">Inactivo</span>{% endif %}</td>
                <td>
                    {% if u.username != session.get('user') %}
                    <form method="POST" action="/admin/toggle/{{ u.id }}">
                        <button type="submit" class="{% if u.activo %}btn-toggle{% else %}btn-active{% endif %}">
                            {% if u.activo %}Desactivar{% else %}Activar{% endif %}
                        </button>
                    </form>
                    {% else %}
                    <small style="color:#8e85b8;">Tu Cuenta</small>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

# === RUTAS ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usr = request.form.get('username', '').strip()
        pwd = request.form.get('password', '').strip()
        user = validar_usuario(usr, pwd)
        if user:
            session.permanent = True
            session['user'] = user['username']
            session['role'] = user.get('role', 'user')
            print(f"🔑 Sesion iniciada correctamente para: {session['user']} con rol {session['role']}")
            return redirect(url_for('index'))
        return render_template_string(HTML_LOGIN, error="Usuario o contraseña incorrectos / Cuenta pendiente de activación")
    return render_template_string(HTML_LOGIN)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usr = request.form.get('username', '').strip()
        pwd = request.form.get('password', '').strip()
        try:
            exist = supabase.table('usuarios').select('*').eq('username', usr).execute()
            if exist.data and len(exist.data) > 0:
                return render_template_string(HTML_REGISTER, error="El nombre de usuario ya está ocupado")
            
            supabase.table('usuarios').insert({'username': usr, 'password': pwd, 'activo': False, 'role': 'user'}).execute()
            return render_template_string(HTML_LOGIN, msg="✅ Registro solicitado. El administrador debe activar tu cuenta.")
        except Exception as e:
            return render_template_string(HTML_REGISTER, error=f"Error al registrar: {e}")
    return render_template_string(HTML_REGISTER)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template_string(HTML_LAYOUT)

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    res = supabase.table('usuarios').select('*').execute()
    return render_template_string(HTML_ADMIN, usuarios=res.data)

@app.route('/admin/crear', methods=['POST'])
def admin_crear():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    usr = request.form.get('username', '').strip()
    pwd = request.form.get('password', '').strip()
    supabase.table('usuarios').insert({'username': usr, 'password': pwd, 'activo': True, 'role': 'user'}).execute()
    return redirect(url_for('admin'))

@app.route('/admin/toggle/<int:user_id>', methods=['POST'])
def admin_toggle(user_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    res = supabase.table('usuarios').select('activo').eq('id', user_id).execute()
    if res.data:
        estado_actual = res.data[0]['activo']
        supabase.table('usuarios').update({'activo': not estado_actual}).eq('id', user_id).execute()
    return redirect(url_for('admin'))

@app.route('/api/bot-auth', methods=['POST'])
def bot_auth():
    data = request.get_json() or {}
    usr = data.get("username", "").strip()
    pwd = data.get("password", "").strip()
    user = validar_usuario(usr, pwd)
    if user:
        return jsonify({"status": "ok", "message": "Autorizado"}), 200
    return jsonify({"status": "error", "message": "Credenciales inválidas o cuenta desactivada"}), 401

@app.route('/api/timers', methods=['GET'])
def get_timers():
    if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
    timers_map, pcs_map, pj_map, hb_map = obtener_datos_nube()
    return jsonify({"timers": timers_map, "cooldowns": COOLDOWNS, "servers": SERVIDORES, "ultimas_pcs": pcs_map, "ultimos_pjs": pj_map, "heartbeats": hb_map})

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json() or {}
    svr, pc_id, pj_name = data.get("server"), data.get("pc_id", "Desconocida"), data.get("pj_name", "Desconocido")
    if svr in SERVIDORES:
        actualizar_heartbeat_nube(svr, pc_id, pj_name)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/kill', methods=['POST'])
def kill_boss():
    data = request.get_json() or {}
    svr, boss, pc_id, pj_name = data.get("server"), data.get("boss"), data.get("pc_id", "Desconocida"), data.get("pj_name", "Desconocido")
    if svr in SERVIDORES and boss in COOLDOWNS:
        guardar_boss_nube(svr, boss, pc_id, pj_name)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_boss():
    data = request.get_json() or {}
    svr, boss = data.get("server"), data.get("boss")
    if svr in SERVIDORES:
        borrar_boss_nube(svr, boss)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
