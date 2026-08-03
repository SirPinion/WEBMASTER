import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# === CONFIGURACIÓN DE BOSSES Y COOLDOWNS (En Minutos) ===
COOLDOWNS = {
    "Muggron": 180, 
    "Kharzul": 420, 
    "Vescrya": 420,
    "Borgar": 120, 
    "Dreadhorn": 60, 
    "Moltragon": 60
}

SERVIDORES = ["Server 1", "Server 2", "Server 3"]
RUTA_RESPALDO = "backup_timers.json"

timers_servidores = {svr: {} for svr in SERVIDORES}

# Cargar timers desde el disco al iniciar
if os.path.exists(RUTA_RESPALDO):
    try:
        with open(RUTA_RESPALDO, "r") as f:
            datos = json.load(f)
            for svr, bosses in datos.items():
                if svr in timers_servidores:
                    for boss, dt_str in bosses.items():
                        dt_obj = datetime.fromisoformat(dt_str)
                        if dt_obj > datetime.now():
                            timers_servidores[svr][boss] = dt_obj
        print("✅ Respaldo cargado correctamente.")
    except Exception as e:
        print(f"⚠️ Error cargando respaldo: {e}")

def guardar_datos():
    try:
        datos = {
            svr: {boss: dt.isoformat() for boss, dt in bosses.items()}
            for svr, bosses in timers_servidores.items()
        }
        with open(RUTA_RESPALDO, "w") as f:
            json.dump(datos, f, indent=4)
    except Exception as e:
        print(f"❌ Error al guardar datos: {e}")

# === INTERFAZ WEB COMPLETA ===
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ TIMERS DE BOSSES MUDREAM ⚔️</title>
    <style>
        :root {
            --bg-color: #0c0a17;
            --card-bg: #16122b;
            --accent-purple: #7b2cbf;
            --accent-hover: #9d4edd;
            --text-main: #e2d9ff;
            --alive-color: #2ecc71;
            --cd-color: #ff4757;
        }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        h1 {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 20px;
            text-shadow: 0 0 10px rgba(123, 44, 191, 0.5);
        }

        /* NAVEGACIÓN POR PESTAÑAS DE SERVIDOR */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 25px;
        }

        .tab-btn {
            background: #241e42;
            border: 2px solid #3c326e;
            color: #fff;
            padding: 12px 24px;
            font-size: 1.1rem;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .tab-btn.active {
            background: var(--accent-purple);
            border-color: var(--accent-hover);
            box-shadow: 0 0 12px rgba(157, 78, 221, 0.6);
        }

        /* GRILLA DE BOSSES */
        .boss-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1000px;
        }

        .boss-card {
            background: var(--card-bg);
            border: 1px solid #2e2659;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            transition: transform 0.2s;
        }

        .boss-card:hover {
            transform: translateY(-3px);
        }

        .boss-title {
            font-size: 1.4rem;
            font-weight: bold;
            margin-bottom: 5px;
            color: #ffffff;
        }

        .boss-cd-info {
            font-size: 0.85rem;
            color: #8c82b0;
            margin-bottom: 15px;
        }

        .timer-display {
            font-family: 'Courier New', Courier, monospace;
            font-size: 1.8rem;
            font-weight: bold;
            margin-bottom: 15px;
            padding: 10px 15px;
            border-radius: 6px;
            background: #0d0a1a;
            width: 80%;
            text-align: center;
        }

        .status-alive {
            color: var(--alive-color);
            border: 1px solid var(--alive-color);
        }

        .status-cooldown {
            color: var(--cd-color);
            border: 1px solid var(--cd-color);
        }

        .btn-kill {
            background: var(--accent-purple);
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 1rem;
            font-weight: bold;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        }

        .btn-kill:hover {
            background: var(--accent-hover);
        }

        .btn-reset {
            background: #3a325c;
            color: #aaa;
            border: none;
            padding: 6px 12px;
            font-size: 0.8rem;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 8px;
        }

        .btn-reset:hover {
            background: #ff4757;
            color: white;
        }

        @media (max-width: 600px) {
            .tabs { flex-direction: column; width: 100%; }
            .tab-btn { width: 100%; }
        }
    </style>
</head>
<body>

    <h1>⚔️ MONITOR DE TIMERS - MUDREAM ⚔️</h1>

    <!-- Pestañas de Servidor -->
    <div class="tabs">
        <button class="tab-btn active" onclick="cambiarServidor('Server 1')">Server 1</button>
        <button class="tab-btn" onclick="cambiarServidor('Server 2')">Server 2</button>
        <button class="tab-btn" onclick="cambiarServidor('Server 3')">Server 3</button>
    </div>

    <!-- Grilla de Tarjetas -->
    <div class="boss-grid" id="bossContainer">
        <!-- Renderizado dinámico desde JavaScript -->
    </div>

    <script>
        let servidorActual = "Server 1";
        let datosServidores = {};

        function cambiarServidor(serverName) {
            servidorActual = serverName;
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.toggle('active', btn.innerText === serverName);
            });
            renderizarUI();
        }

        async function obtenerTimers() {
            try {
                const response = await fetch('/api/timers');
                datosServidores = await response.json();
                renderizarUI();
            } catch (err) {
                console.error("Error al obtener timers:", err);
            }
        }

        async function registrarKill(bossName) {
            try {
                await fetch('/api/kill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server: servidorActual, boss: bossName })
                });
                obtenerTimers();
            } catch (err) {
                console.error("Error al registrar kill:", err);
            }
        }

        async function reiniciarTimer(bossName) {
            try {
                await fetch('/api/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server: servidorActual, boss: bossName })
                });
                obtenerTimers();
            } catch (err) {
                console.error("Error al reiniciar timer:", err);
            }
        }

        function renderizarUI() {
            const container = document.getElementById('bossContainer');
            container.innerHTML = '';

            const bossesServer = datosServidores.timers ? (datosServidores.timers[servidorActual] || {}) : {};
            const cooldowns = datosServidores.cooldowns || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);

            for (const [bossName, cdMinutos] of Object.entries(cooldowns)) {
                let htmlTimer = '';
                let esCooldown = false;

                if (bossName in bossesServer) {
                    const targetUnix = bossesServer[bossName];
                    const diffSegundos = targetUnix - ahoraUnix;

                    if (diffSegundos > 0) {
                        esCooldown = true;
                        const h = Math.floor(diffSegundos / 3600);
                        const m = Math.floor((diffSegundos % 3600) / 60);
                        const s = diffSegundos % 60;

                        const formatH = h > 0 ? `${h}h ` : '';
                        const formatM = m < 10 ? `0${m}` : m;
                        const formatS = s < 10 ? `0${s}` : s;

                        htmlTimer = `<div class="timer-display status-cooldown">🔴 ${formatH}${formatM}m ${formatS}s</div>`;
                    }
                }

                if (!esCooldown) {
                    htmlTimer = `<div class="timer-display status-alive">🟢 ¡VIVO!</div>`;
                }

                const cardHtml = `
                    <div class="boss-card">
                        <div class="boss-title">${bossName}</div>
                        <div class="boss-cd-info">Respawn: ${cdMinutos} min</div>
                        ${htmlTimer}
                        <button class="btn-kill" onclick="registrarKill('${bossName}')">⚔️ REGISTRAR MUERTE</button>
                        ${esCooldown ? `<button class="btn-reset" onclick="reiniciarTimer('${bossName}')">Limpiar Timer</button>` : ''}
                    </div>
                `;

                container.innerHTML += cardHtml;
            }
        }

        // Bucle de actualización continua en vivo (1 segundo)
        setInterval(obtenerTimers, 1000);
        obtenerTimers();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

@app.route('/api/timers', methods=['GET'])
def get_timers():
    respuesta = {}
    ahora = datetime.now()
    for svr, bosses in timers_servidores.items():
        respuesta[svr] = {
            boss: int(dt.timestamp()) 
            for boss, dt in bosses.items() 
            if dt > ahora
        }
    return jsonify({"timers": respuesta, "cooldowns": COOLDOWNS})

@app.route('/api/kill', methods=['POST'])
def kill_boss():
    data = request.get_json()
    svr = data.get("server")
    boss = data.get("boss")
    if svr in timers_servidores and boss in COOLDOWNS:
        timers_servidores[svr][boss] = datetime.now() + timedelta(minutes=COOLDOWNS[boss])
        guardar_datos()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_boss():
    data = request.get_json()
    svr = data.get("server")
    boss = data.get("boss")
    if svr in timers_servidores and boss in timers_servidores[svr]:
        del timers_servidores[svr][boss]
        guardar_datos()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    # Ejecución local para pruebas
    app.run(host='0.0.0.0', port=5000, debug=True)