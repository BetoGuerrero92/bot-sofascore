import os
import json
import time
import requests
import threading
import numpy as np
from datetime import datetime, timedelta
from flask import Flask
from curl_cffi import requests as cffi_requests
from apscheduler.schedulers.background import BackgroundScheduler

# ==============================================================================
# SERVIDOR WEB PARA MANTENER RENDER ACTIVO (KEEP-ALIVE)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot SofaScore + Montecarlo activo y corriendo 24/7", 200

def ejecutar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==============================================================================
# CONFIGURACIÓN Y LISTA OFICIAL DE LIGAS Y TORNEOS
# ==============================================================================
TELEGRAM_TOKEN = '8981343928:AAGkvLxUoHt4tSLP7x20a5QOOTBgnJqruaI'
CHAT_ID_DESTINO = ''

LIGAS_PERMITIDAS = [
    "Premier League", "EFL Cup", "Carabao Cup",
    "Serie A", "Coppa Italia", "Copa Italia",
    "LaLiga", "Liga Espanola", "Copa del Rey", "Supercopa de Espana", "Supercopa",
    "Bundesliga", "DFB Pokal", "DFB-Pokal",
    "Ligue 1", "Coupe de France", "Copa de Francia",
    "Pro League", "Jupiler Pro League", "Super Lig", "Süper Lig", "Superliga",
    "Eredivisie", "Eredivise", "Primeira Liga", "Liga Portugal", "Saudi Pro League", "Liga Profesional Saudi",
    "UEFA Champions League", "Champions League", "UEFA Europa League", "Europa League",
    "UEFA Conference League", "Conference League",
    "UEFA Nations League", "Nations League", "CONCACAF Nations League",
    "Liga MX"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.sofascore.com/',
}

ARCHIVO_HISTORIAL = 'analizados.txt'
ARCHIVO_MONITOREO = 'monitoreo.json'
ARCHIVO_LIVE_CACHE = 'live_cache.json'

# ==============================================================================
# MANEJO DE ARCHIVOS Y ESTADO
# ==============================================================================
def cargar_analizados():
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return set()
    with open(ARCHIVO_HISTORIAL, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def guardar_analizado(event_id):
    with open(ARCHIVO_HISTORIAL, 'a') as f:
        f.write(f"{event_id}\n")

def cargar_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def guardar_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def es_torneo_permitido(event):
    if not LIGAS_PERMITIDAS:
        return True
    tournament_name = event.get('tournament', {}).get('name', '')
    category_name = event.get('tournament', {}).get('category', {}).get('name', '')
    texto_completo = f"{tournament_name} {category_name}".lower()
    
    for liga in LIGAS_PERMITIDAS:
        if liga.lower() in texto_completo:
            return True
    return False

def enviar_telegram(chat_id, texto):
    if not chat_id:
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': texto, 'parse_mode': 'Markdown'}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

# ==============================================================================
# APIS SOFASCORE
# ==============================================================================
def obtener_datos_partido(event_id):
    url = f'https://api.sofascore.com/api/v1/event/{event_id}'
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=6)
        if r.status_code == 200:
            data = r.json().get('event', {})
            return {
                'id': str(event_id),
                'home_id': data.get('homeTeam', {}).get('id'),
                'away_id': data.get('awayTeam', {}).get('id'),
                'home_name': data.get('homeTeam', {}).get('name', 'Local'),
                'away_name': data.get('awayTeam', {}).get('name', 'Visitante'),
                'tournament': data.get('tournament', {}).get('name', 'Torneo'),
                'start_timestamp': data.get('startTimestamp')
            }
    except Exception:
        pass
    return None

def obtener_bajas_sofascore(event_id):
    url = f'https://api.sofascore.com/api/v1/event/{event_id}/lineups'
    bajas = {'home': [], 'away': []}
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=6)
        if r.status_code == 200:
            data = r.json()
            for side in ['home', 'away']:
                missing = data.get(side, {}).get('missingPlayers', [])
                for p in missing:
                    player_info = p.get('player', {})
                    bajas[side].append({
                        'name': player_info.get('name', 'Jugador'),
                        'position': player_info.get('position', 'F'),
                        'reason': p.get('reason', 'Baja')
                    })
    except Exception:
        pass
    return bajas

def extraer_promedios_equipo(team_id):
    if not team_id:
        return {'gf': 1.4, 'gc': 1.1, 'g1t': 0.6, 'corn': 4.8, 'card': 2.1}
    try:
        url = f'https://api.sofascore.com/api/v1/team/{team_id}/events/last/0'
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=6)
        if r.status_code != 200:
            return {'gf': 1.4, 'gc': 1.1, 'g1t': 0.6, 'corn': 4.8, 'card': 2.1}
        
        events = r.json().get('events', [])
        partidos = [e for e in events if e.get('status', {}).get('type') == 'finished'][:5]
        if not partidos:
            return {'gf': 1.4, 'gc': 1.1, 'g1t': 0.6, 'corn': 4.8, 'card': 2.1}
        
        gf_l, gc_l, g1t_l, corn_l, card_l = [], [], [], [], []
        for p in partidos:
            is_home = p.get('homeTeam', {}).get('id') == team_id
            gf = p.get('homeScore', {}).get('current', 1) if is_home else p.get('awayScore', {}).get('current', 1)
            gc = p.get('awayScore', {}).get('current', 1) if is_home else p.get('homeScore', {}).get('current', 1)
            g1t = p.get('homeScore', {}).get('period1', 0) if is_home else p.get('awayScore', {}).get('period1', 0)
            
            gf_l.append(gf if gf is not None else 1)
            gc_l.append(gc if gc is not None else 1)
            g1t_l.append(g1t if g1t is not None else 0)
            
            try:
                p_id = p.get('id')
                url_s = f'https://api.sofascore.com/api/v1/event/{p_id}/statistics'
                r_s = cffi_requests.get(url_s, headers=HEADERS, impersonate='chrome120', timeout=3)
                if r_s.status_code == 200:
                    stats = r_s.json().get('statistics', [])
                    if stats:
                        for g in stats[0].get('groups', []):
                            for item in g.get('statisticsItems', []):
                                name = item.get('name', '').lower()
                                if 'corner' in name or 'tiros de esquina' in name:
                                    val = item.get('home') if is_home else item.get('away')
                                    if val is not None: corn_l.append(float(val))
                                if 'card' in name or 'tarjetas' in name:
                                    val = item.get('home') if is_home else item.get('away')
                                    if val is not None: card_l.append(float(val))
            except Exception:
                continue
                
        return {
            'gf': float(np.mean(gf_l)) if gf_l else 1.4,
            'gc': float(np.mean(gc_l)) if gc_l else 1.1,
            'g1t': float(np.mean(g1t_l)) if g1t_l else 0.6,
            'corn': float(np.mean(corn_l)) if corn_l else 4.8,
            'card': float(np.mean(card_l)) if card_l else 2.1
        }
    except Exception:
        return {'gf': 1.4, 'gc': 1.1, 'g1t': 0.6, 'corn': 4.8, 'card': 2.1}

# ==============================================================================
# MOTOR MONTE CARLO PRE-PARTIDO
# ==============================================================================
def simular_pre_partido(info, bajas_detectadas=None):
    st_h = extraer_promedios_equipo(info['home_id'])
    st_a = extraer_promedios_equipo(info['away_id'])
    
    fact_gf_h, fact_gc_h = 1.0, 1.0
    fact_gf_a, fact_gc_a = 1.0, 1.0
    
    if bajas_detectadas:
        for b in bajas_detectadas.get('home', []):
            pos = b.get('position', 'F')
            if pos in ['F', 'M']: fact_gf_h *= 0.88
            elif pos in ['D', 'G']: fact_gc_h *= 1.12
        for b in bajas_detectadas.get('away', []):
            pos = b.get('position', 'F')
            if pos in ['F', 'M']: fact_gf_a *= 0.88
            elif pos in ['D', 'G']: fact_gc_a *= 1.12

    sim = 100000
    exp_gh = max(0.2, ((st_h['gf'] * fact_gf_h) + (st_a['gc'] * fact_gc_a)) / 2.0)
    exp_ga = max(0.2, ((st_a['gf'] * fact_gf_a) + (st_h['gc'] * fact_gc_h)) / 2.0)
    
    gh = np.random.poisson(exp_gh, sim)
    ga = np.random.poisson(exp_ga, sim)
    g1t_h = np.random.poisson(max(0.1, st_h['g1t'] * fact_gf_h), sim)
    g1t_a = np.random.poisson(max(0.1, st_a['g1t'] * fact_gf_a), sim)
    tot_1t = g1t_h + g1t_a
    g2t_h = np.maximum(0, gh - g1t_h)
    g2t_a = np.maximum(0, ga - g1t_a)
    
    ch = np.random.poisson(max(1.0, st_h['corn']), sim)
    ca = np.random.poisson(max(1.0, st_a['corn']), sim)
    tot_corn = ch + ca
    th = np.random.poisson(max(0.5, st_h['card']), sim)
    ta = np.random.poisson(max(0.5, st_a['card']), sim)
    tot_card = th + ta
    
    p_h = (np.sum(gh > ga) / sim) * 100
    p_d = (np.sum(gh == ga) / sim) * 100
    p_a = (np.sum(ga > gh) / sim) * 100
    p_1x = p_h + p_d
    p_x2 = p_a + p_d
    p_12 = p_h + p_a
    p_btts_si = (np.sum((gh > 0) & (ga > 0)) / sim) * 100
    p_btts_no = 100.0 - p_btts_si
    p_o15 = (np.sum((gh + ga) > 1.5) / sim) * 100
    p_o25 = (np.sum((gh + ga) > 2.5) / sim) * 100
    p_u25 = 100.0 - p_o25
    p_o35 = (np.sum((gh + ga) > 3.5) / sim) * 100
    p_o05_1t = (np.sum(tot_1t > 0.5) / sim) * 100
    p_o15_1t = (np.sum(tot_1t > 1.5) / sim) * 100
    p_1st_h = (np.sum(gh > 0) / sim) * 100
    p_1st_a = (np.sum(ga > 0) / sim) * 100
    p_sin_gol = (np.sum((gh == 0) & (ga == 0)) / sim) * 100
    p_h_1t = (np.sum(g1t_h > g1t_a) / sim) * 100
    p_d_1t = (np.sum(g1t_h == g1t_a) / sim) * 100
    p_a_1t = (np.sum(g1t_a > g1t_h) / sim) * 100
    avg_corn_tot = float(np.mean(tot_corn))
    p_o85_c = (np.sum(tot_corn > 8.5) / sim) * 100
    p_o95_c = (np.sum(tot_corn > 9.5) / sim) * 100
    avg_corn_h = float(np.mean(ch))
    avg_corn_a = float(np.mean(ca))
    avg_card_tot = float(np.mean(tot_card))
    p_o35_t = (np.sum(tot_card > 3.5) / sim) * 100
    p_o45_t = (np.sum(tot_card > 4.5) / sim) * 100
    avg_card_h = float(np.mean(th))
    avg_card_a = float(np.mean(ta))
    p_win_half_h = (np.sum((g1t_h > g1t_a) | (g2t_h > g2t_a)) / sim) * 100
    p_win_half_a = (np.sum((g1t_a > g1t_h) | (g2t_a > g2t_h)) / sim) * 100
    
    o_h = 100 / p_h if p_h > 0 else 99
    o_d = 100 / p_d if p_d > 0 else 99
    o_a = 100 / p_a if p_a > 0 else 99
    o_btts = 100 / p_btts_si if p_btts_si > 0 else 99
    o_o25 = 100 / p_o25 if p_o25 > 0 else 99

    fecha_partido = ""
    if info.get('start_timestamp'):
        fecha_partido = datetime.fromtimestamp(info['start_timestamp']).strftime('%Y-%m-%d %H:%M')

    texto = f"""==================================
ANALISIS AUTOMATICO (100k SIMS)
{info['home_name']} vs {info['away_name']}
Torneo: {info['tournament']}
Fecha: {fecha_partido}
==================================

1. MONEY LINE (1X2)
- {info['home_name']}: {p_h:.1f}%
- Empate: {p_d:.1f}%
- {info['away_name']}: {p_a:.1f}%

2. DOBLE OPORTUNIDAD
- 1X (Local o Empate): {p_1x:.1f}%
- X2 (Empate o Visitante): {p_x2:.1f}%
- 12 (Sin Empate): {p_12:.1f}%

3. BOTH TEAMS TO SCORE (BTTS)
- BTTS Si: {p_btts_si:.1f}%
- BTTS No: {p_btts_no:.1f}%

4. OVER / UNDER GOLES TOTALES
- Over 1.5 Goles: {p_o15:.1f}%
- Over 2.5 Goles: {p_o25:.1f}% (Under 2.5: {p_u25:.1f}%)
- Over 3.5 Goles: {p_o35:.1f}%

5. OVER / UNDER 1ER TIEMPO
- Over 0.5 Goles 1T: {p_o05_1t:.1f}%
- Over 1.5 Goles 1T: {p_o15_1t:.1f}%

6. PRIMER EQUIPO EN ANOTAR
- {info['home_name']}: {p_1st_h:.1f}%
- {info['away_name']}: {p_1st_a:.1f}%
- Sin Goles (0-0): {p_sin_gol:.1f}%

7. GANADOR 1ER TIEMPO (1X2 1T)
- {info['home_name']} 1T: {p_h_1t:.1f}%
- Empate 1T: {p_d_1t:.1f}%
- {info['away_name']} 1T: {p_a_1t:.1f}%

8. CORNERS TOTALES DEL PARTIDO
- Promedio Esperado: {avg_corn_tot:.1f} corners
- Over 8.5 Corners: {p_o85_c:.1f}%
- Over 9.5 Corners: {p_o95_c:.1f}%

9. CORNERS INDIVIDUALES POR EQUIPO
- {info['home_name']}: {avg_corn_h:.1f} corners avg
- {info['away_name']}: {avg_corn_a:.1f} corners avg

10. TARJETAS TOTALES DEL PARTIDO
- Promedio Esperado: {avg_card_tot:.1f} tarjetas
- Over 3.5 Tarjetas: {p_o35_t:.1f}%
- Over 4.5 Tarjetas: {p_o45_t:.1f}%

11. TARJETAS INDIVIDUALES POR EQUIPO
- {info['home_name']}: {avg_card_h:.1f} tarjetas avg
- {info['away_name']}: {avg_card_a:.1f} tarjetas avg

12. GANA AL MENOS UN TIEMPO
- {info['home_name']}: {p_win_half_h:.1f}%
- {info['away_name']}: {p_win_half_a:.1f}%

13. CUOTAS JUSTAS (FAIR ODDS 1X2)
- Local: @{o_h:.2f}
- Empate: @{o_d:.2f}
- Visitante: @{o_a:.2f}

14. CUOTAS JUSTAS (BTTS / OVER 2.5)
- BTTS Si: @{o_btts:.2f}
- Over 2.5 Goles: @{o_o25:.2f}
=================================="""

    return texto, {'p_h': p_h, 'p_o25': p_o25, 'o_h': o_h, 'o_d': o_d, 'o_a': o_a}

# ==============================================================================
# BARRIDO DIARIO PASIVO
# ==============================================================================
def barrido_diario_pasivo():
    global CHAT_ID_DESTINO
    if not CHAT_ID_DESTINO:
        return

    analizados = cargar_analizados()
    monitoreo = cargar_json(ARCHIVO_MONITOREO)
    hoy = datetime.now()
    dias_a_revisar = [hoy + timedelta(days=i) for i in range(6)]
    
    print(f"\n🌙 [PLANO PASIVO] Analizando agenda de próximos 5 días...")
    nuevos = 0

    for fecha_dt in dias_a_revisar:
        fecha_str = fecha_dt.strftime('%Y-%m-%d')
        url = f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{fecha_str}'
        try:
            r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=8)
            if r.status_code == 200:
                events = r.json().get('events', [])
                for e in events:
                    evt_id = str(e.get('id'))
                    status = e.get('status', {}).get('type')
                    
                    if status == 'notstarted' and es_torneo_permitido(e):
                        if evt_id not in analizados:
                            info = obtener_datos_partido(evt_id)
                            if info:
                                bajas = obtener_bajas_sofascore(evt_id)
                                reporte, res = simular_pre_partido(info, bajas)
                                enviar_telegram(CHAT_ID_DESTINO, reporte)
                                
                                guardar_analizado(evt_id)
                                analizados.add(evt_id)
                                monitoreo[evt_id] = {'home': info['home_name'], 'away': info['away_name'], 'res': res, 'bajas': bajas}
                                nuevos += 1
                                time.sleep(2)
        except Exception as err:
            print(f"Error en barrido diario {fecha_str}: {err}")
            
    guardar_json(ARCHIVO_MONITOREO, monitoreo)

# ==============================================================================
# ESCÁNER EN VIVO
# ==============================================================================
def obtener_datos_live(event_id):
    url = f'https://api.sofascore.com/api/v1/event/{event_id}'
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=5)
        if r.status_code == 200:
            d = r.json().get('event', {})
            status = d.get('status', {}).get('type')
            
            minuto = 45
            time_info = d.get('time', {})
            if 'currentPeriodStartTimestamp' in time_info:
                elapsed = (datetime.now().timestamp() - time_info['currentPeriodStartTimestamp']) / 60
                period = d.get('status', {}).get('description', '')
                if '1st' in period: minuto = min(45, int(elapsed))
                elif '2nd' in period: minuto = min(90, 45 + int(elapsed))
            
            return {
                'status': status,
                'minuto': max(1, min(90, minuto)),
                'home_score': d.get('homeScore', {}).get('current', 0),
                'away_score': d.get('awayScore', {}).get('current', 0),
                'home_name': d.get('homeTeam', {}).get('name', 'Local'),
                'away_name': d.get('awayTeam', {}).get('name', 'Visitante'),
                'tournament': d.get('tournament', {}).get('name', 'Torneo')
            }
    except Exception:
        pass
    return None

def obtener_incidencias_live(event_id):
    url = f'https://api.sofascore.com/api/v1/event/{event_id}/incidents'
    inc = {'rojas_h': 0, 'rojas_a': 0, 'eventos': []}
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=5)
        if r.status_code == 200:
            items = r.json().get('incidents', [])
            for item in items:
                if item.get('incidentType') == 'card' and item.get('cardClass') in ['red', 'yellowRed']:
                    is_h = item.get('isHome', True)
                    if is_h: inc['rojas_h'] += 1
                    else: inc['rojas_a'] += 1
                    inc['eventos'].append(f"🔴 Tarjeta Roja {'Local' if is_h else 'Visitante'} (Min {item.get('time', '?')}')")
    except Exception:
        pass
    return inc

def obtener_stats_live(event_id):
    url = f'https://api.sofascore.com/api/v1/event/{event_id}/statistics'
    st = {'corn_h': 0, 'corn_a': 0, 'card_h': 0, 'card_a': 0, 'shots_h': 0, 'shots_a': 0}
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=5)
        if r.status_code == 200:
            groups = r.json().get('statistics', [])
            if groups:
                for g in groups[0].get('groups', []):
                    for item in g.get('statisticsItems', []):
                        name = item.get('name', '').lower()
                        if 'corner' in name or 'tiros de esquina' in name:
                            st['corn_h'] = float(item.get('home', 0))
                            st['corn_a'] = float(item.get('away', 0))
                        elif 'card' in name or 'tarjetas' in name:
                            st['card_h'] = float(item.get('home', 0))
                            st['card_a'] = float(item.get('away', 0))
                        elif 'shots on target' in name or 'tiros a puerta' in name:
                            st['shots_h'] = float(item.get('home', 0))
                            st['shots_a'] = float(item.get('away', 0))
    except Exception:
        pass
    return st

def escanear_partidos_en_vivo():
    global CHAT_ID_DESTINO
    if not CHAT_ID_DESTINO:
        return

    url = 'https://api.sofascore.com/api/v1/sport/football/events/live'
    cache_live = cargar_json(ARCHIVO_LIVE_CACHE)
    
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate='chrome120', timeout=8)
        if r.status_code == 200:
            events = r.json().get('events', [])
            for e in events:
                evt_id = str(e.get('id'))
                if es_torneo_permitido(e):
                    info_live = obtener_datos_live(evt_id)
                    if not info_live or info_live['minuto'] < 12 or info_live['minuto'] > 85:
                        continue
                        
                    inc = obtener_incidencias_live(evt_id)
                    st = obtener_stats_live(evt_id)
                    
                    minuto = info_live['minuto']
                    tot_corn_actual = st['corn_h'] + st['corn_a']
                    tot_card_actual = st['card_h'] + st['card_a']
                    tot_rojas = inc['rojas_h'] + inc['rojas_a']
                    
                    data_prev = cache_live.get(evt_id, {'rojas': 0, 'last_alert_min': 0})
                    
                    es_nueva_roja = tot_rojas > data_prev.get('rojas', 0)
                    es_asedio_corners = (minuto >= 50 and tot_corn_actual >= 6 and (minuto - data_prev.get('last_alert_min', 0)) >= 20)
                    es_partido_caliente = (minuto >= 40 and tot_card_actual >= 4 and (minuto - data_prev.get('last_alert_min', 0)) >= 25)
                    
                    if es_nueva_roja or es_asedio_corners or es_partido_caliente:
                        rem_pct = (90.0 - minuto) / 90.0
                        exp_corn_rem = 4.5 * rem_pct * (1.35 if es_asedio_corners else 1.0)
                        exp_card_rem = 2.5 * rem_pct * (1.30 if es_partido_caliente else 1.0)
                        
                        proj_corn = tot_corn_actual + exp_corn_rem
                        proj_card = tot_card_actual + exp_card_rem
                        
                        linea_c = int(np.round(proj_corn))
                        linea_t = int(np.round(proj_card))
                        
                        msg = f"""⚡ OPORTUNIDAD EN CORTO (EN VIVO) ⚡
⚽ {info_live['home_name']} {info_live['home_score']} - {info_live['away_score']} {info_live['away_name']}
🏆 Torneo: {info_live['tournament']}
⏱️ Minuto: {minuto}'

📊 Métricas en Vivo:
* Córners actual: {int(st['corn_h'])} - {int(st['corn_a'])} (Total: {int(tot_corn_actual)})
* Tarjetas actual: {int(st['card_h'])} - {int(st['card_a'])} (Total: {int(tot_card_actual)})
* Tiros a Puerta: {int(st['shots_h'])} - {int(st['shots_a'])}
"""
                        if inc['eventos']:
                            msg += "\n🚨 Incidencia Crítica: " + " | ".join(inc['eventos']) + "\n"

                        msg += f"""
🎯 SUGERENCIA EN CALIENTE:
🚩 *Córners:* Buscar línea *Over {linea_c - 0.5}* (Proyección final: {proj_corn:.1f})
🟨 *Tarjetas:* Buscar línea *Over {linea_t - 0.5}* (Proyección final: {proj_card:.1f})
"""
                        enviar_telegram(CHAT_ID_DESTINO, msg)
                        
                        cache_live[evt_id] = {
                            'rojas': tot_rojas,
                            'last_alert_min': minuto
                        }
                        guardar_json(ARCHIVO_LIVE_CACHE, cache_live)
                        time.sleep(2)
                        
    except Exception:
        pass

# ==============================================================================
# INICIALIZACIÓN
# ==============================================================================
def obtener_chat_id():
    global CHAT_ID_DESTINO
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            results = r.json().get('result', [])
            if results:
                CHAT_ID_DESTINO = results[-1].get('message', {}).get('chat', {}).get('id')
    except Exception:
        pass

def iniciar_bot():
    print("🚀 BOT QUANTITATIVO EN EJECUCIÓN (MODO RENDER CLOUD 24/7)")
    obtener_chat_id()
    
    barrido_diario_pasivo()

    scheduler = BackgroundScheduler()
    scheduler.add_job(escanear_partidos_en_vivo, 'interval', minutes=2)
    scheduler.add_job(barrido_diario_pasivo, 'cron', hour=23, minute=0)
    scheduler.start()

    last_update_id = 0
    url_updates = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates'
    
    while True:
        try:
            r = requests.get(url_updates, params={'offset': last_update_id + 1, 'timeout': 10})
            if r.status_code == 200:
                data = r.json()
                for result in data.get('result', []):
                    last_update_id = result['update_id']
                    message = result.get('message', {})
                    chat_id = message.get('chat', {}).get('id')
                    text = message.get('text', '')

                    if chat_id:
                        global CHAT_ID_DESTINO
                        CHAT_ID_DESTINO = chat_id

                    if text in ['/start', '/barrido']:
                        enviar_telegram(chat_id, "⏳ Ejecutando barrido pre-partido manual...")
                        barrido_diario_pasivo()
                    elif text in ['/live', '/envivo']:
                        enviar_telegram(chat_id, "⚡ Escaneando partidos en vivo de tus ligas...")
                        escanear_partidos_en_vivo()
        except Exception:
            pass
        time.sleep(2)

if _name_ == '_main_':
    # Iniciar servidor web Flask en segundo plano para Render
    threading.Thread(target=ejecutar_servidor_web, daemon=True).start()
    # Iniciar motor del bot
    iniciar_bot()
