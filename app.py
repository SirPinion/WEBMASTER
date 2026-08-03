import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# Configuración de Bosses y sus respawns en minutos
COOLDOWNS = {
    "Muggron": 180, 
    "Kharzul": 420, 
    "Vescrya": 420,
    "Borgar": 120, 
    "Dreadhorn": 60, 
    "Moltragon": 60
}

SERVIDORES = ["Server 1", "Server 2", "Server 3", "Server 20"]
RUTA_RESPALDO = "backup_timers.json"

timers_servidores = {svr: {} for svr in SERVIDORES}
ultimas_pcs_reportadas = {svr: "Sin reportes" for svr in SERVIDORES}

# Cargar el archivo JSON si existe
if os.path.exists(RUTA_RESPALDO):
    try:
        with open(RUTA_RESPALDO, "r") as f:
            datos = json.load(f)
            for svr, bosses in datos.get("timers", {}).items():
                if svr in timers_servidores:
                    for boss, dt_str in bosses.items():
                        dt_obj = datetime.fromisoformat(dt_str)
                        if dt_obj > datetime.now():
                            timers_servidores[svr][boss] = dt_obj
            ultimas_pcs_reportadas.update(datos.get("pcs", {}))
    except Exception as e:
        print(f"Error cargando respaldo: {e}")

def guardar_disco():
    try:
        datos = {
            "timers": {
                svr: {boss: dt.isoformat() for boss, dt in bosses.items()}
                for svr, bosses in timers_servidores.items()
            },
            "pcs": ultimas_pcs_reportadas
        }
        with open(RUTA_RESPALDO, "w") as f:
            json.dump(datos, f, indent=4)
    except Exception as e:
        print(f"Error guardando respaldo: {e}")

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Monitor Multi-PC - MuDream ⚔️</title>
    <style>
        :root {
            --bg-dark: #0a0814;
            --card-bg: #141126;
            --card-border: #2a244d;
            --accent-purple: #7b2cbf;
            --accent-glow: #9d4edd;
            --text-primary: #e6e1ff;
            --text-secondary: #8e85b8;
            --alive-green: #2ecc71;
            --cd-red: #ff4757;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        header { text-align: center; margin-bottom: 20px; }
        h1 { font-size: 2rem; margin: 0 0 10px 0; color: #fff; text-shadow: 0 0 10px rgba(123, 44, 191, 0.5); }

        .controls-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            margin-bottom: 25px;
            background: #100d21;
            padding: 12px 20px;
            border-radius: 12px;
            border: 1px solid var(--card-border);
        }

        .view-btn {
            background: #1e1938;
            border: 1px solid var(--card-border);
            color: var(--text-primary);
            padding: 10px 18px;
            font-size: 0.95rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .view-btn.active {
            background: var(--accent-purple);
            border-color: var(--accent-glow);
            box-shadow: 0 0 12px rgba(157, 78, 221, 0.5);
            color: #fff;
        }

        .dashboard-container { width: 100%; max-width: 1200px; }

        .grid-all {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }

        .server-block {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }

        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--card-border);
            padding-bottom: 10px;
            margin-bottom: 12px;
        }

        .server-title { font-size: 1.4rem; font-weight: bold; color: #fff; }
        .pc-badge { font-size: 0.75rem; background: #251f47; color: var(--text-secondary); padding: 4px 8px; border-radius: 12px; }

        .boss-list { display: flex; flex-direction: column; gap: 10px; }

        .boss-row {
            background: #0d0a1a;
            border: 1px solid #1f1a3a;
            border-radius: 8px;
            padding: 10px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .boss-name { font-weight: bold; font-size: 1rem; }
        .boss-respawn { font-size: 0.75rem; color: var(--text-secondary); }

        .timer-badge {
            font-family: monospace;
            font-size: 1.1rem;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 6px;
            text-align: center;
        }

        .status-alive { color: var(--alive-green); border: 1px solid var(--alive-green); }
        .status-cd { color: var(--cd-red); border: 1px solid var(--cd-red); }

        .btn-action {
            background: var(--accent-purple);
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }

        .btn-reset { background: #2a2347; color: #aaa; }
        .btn-reset:hover { background: var(--cd-red); color: #fff; }
    </style>
</head>
<body>

    <header>
        <h1>⚔️ MONITOR MULTI-PC - MUDREAM ⚔️</h1>
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
                estadoWeb = await res.json();
                render();
            } catch (e) { console.error("Error obteniendo datos:", e); }
        }

        async function enviarAccion(endpoint, server, boss) {
            try {
                await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server, boss, pc_id: "Navegador Web" })
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
            const ahoraUnix = Math.floor(Date.now() / 1000);

            const servidoresAMostrar = (modoVista === 'TODOS') ? serversDisponibles : [modoVista];
            container.className = (modoVista === 'TODOS') ? "dashboard-container grid-all" : "dashboard-container";

            servidoresAMostrar.forEach(svr => {
                let serverBlock = document.createElement('div');
                serverBlock.className = 'server-block';

                const pcOrigen = ultimosReportes[svr] || 'Sin reportes';

                let htmlContent = `
                    <div class="server-header">
                        <div class="server-title">${svr}</div>
                        <div class="pc-badge">Origen: ${pcOrigen}</div>
                    </div>
                    <div class="boss-list">
                `;

                const bossesServidor = timers[svr] || {};

                for (const [bossName, cdMinutos] of Object.entries(cooldowns)) {
                    let esCooldown = false;
                    let displayTimer = '';

                    if (bossName in bossesServidor) {
                        const targetUnix = bossesServidor[bossName];
                        const diffSec = targetUnix - ahoraUnix;

                        if (diffSec > 0) {
                            esCooldown = true;
                            const h = Math.floor(diffSec / 3600);
                            const m = Math.floor((diffSec % 3600) / 60);
                            const s = diffSec % 60;

                            const strH = h > 0 ? `${h}h ` : '';
                            const strM = m < 10 ? `0${m}` : m;
                            const strS = s < 10 ? `0${s}` : s;

                            displayTimer = `<div class="timer-badge status-cd">🔴 ${strH}${strM}m ${strS}s</div>`;
                        }
                    }

                    if (!esCooldown) {
                        displayTimer = `<div class="timer-badge status-alive">🟢 ¡VIVO!</div>`;
                    }

                    htmlContent += `
                        <div class="boss-row">
                            <div>
                                <div class="boss-name">${bossName}</div>
                                <div class="boss-respawn">${cdMinutos} min</div>
                            </div>
                            ${displayTimer}
                            <div>
                                <button class="btn-action" onclick="enviarAccion('kill', '${svr}', '${bossName}')">⚔️ Kill</button>
                                ${esCooldown ? `<button class="btn-action btn-reset" onclick="enviarAccion('reset', '${svr}', '${bossName}')">✖</button>` : ''}
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
    return jsonify({
        "timers": respuesta, 
        "cooldowns": COOLDOWNS, 
        "servers": SERVIDORES,
        "ultimas_pcs": ultimas_pcs_reportadas
    })

@app.route('/api/kill', methods=['POST'])
def kill_boss():
    data = request.get_json()
    svr = data.get("server")
    boss = data.get("boss")
    pc_id = data.get("pc_id", "Desconocida")

    if svr in timers_servidores and boss in COOLDOWNS:
        timers_servidores[svr][boss] = datetime.now() + timedelta(minutes=COOLDOWNS[boss])
        ultimas_pcs_reportadas[svr] = pc_id
        guardar_disco()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_boss():
    data = request.get_json()
    svr = data.get("server")
    boss = data.get("boss")

    if svr in timers_servidores and boss in timers_servidores[svr]:
        del timers_servidores[svr][boss]
        guardar_disco()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
