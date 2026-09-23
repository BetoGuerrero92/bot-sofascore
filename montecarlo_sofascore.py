import os
import time
import re
import datetime
import threading
import numpy as np
import requests
from curl_cffi import requests as curl_requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

# =========================================================
# CONFIGURACIÓN GENERAL Y CREDENCIALES
# =========================================================
TELEGRAM_BOT_TOKEN = "8981343928:AAGkvLxUoHt4tSLP7x20a5QOOTBgnJqruI"
TELEGRAM_CHAT_ID = "-5173591171"

# Si está vacío, procesa TODOS los partidos de la cartelera sin excepción
LIGAS_OBJETIVO_IDS = []  

app = Flask(__name__)

# =========================================================
# CLIENTE HTTP CON BYPASS CLOUDFLARE (CURL_CFFI)
# =========================================================
def get_scraper():
    session = curl_requests.Session(impersonate="chrome120")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "/",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com"
    })
    return session

# =========================================================
# ENVÍO DE MENSAJES A TELEGRAM
# =========================================================
def send_telegram_message(text, chat_id=None):
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

# =========================================================
# EXTRACCIÓN DE DATOS DE SOFASCORE
# =========================================================
def obtener_partido_por_url(url):
    try:
        ids = re.findall(r'\d+', url)
        if not ids:
            return None
        event_id = ids[-1]
        
        # Corregido: v1 en lugar de v3 para la API de SofaScore
        api_url = f"https://api.sofascore.com/api/v1/event/{event_id}"
        scraper = get_scraper()
        resp = scraper.get(api_url, timeout=10)
        
        # Parámetros por defecto para estadísticas esperadas (Expected Values)
        default_stats = {
            "exp_g_home": 1.6, "exp_g_away": 1.2,
            "exp_c_home": 5.2, "exp_c_away": 4.1,
            "exp_card_home": 2.1, "exp_card_away": 2.4,
            "exp_off_home": 1.8, "exp_off_away": 1.5,
            "exp_sot_home": 4.5, "exp_sot_away": 3.8,
            "exp_st_home": 12.5, "exp_st_away": 10.2,
            "exp_fl_home": 11.5, "exp_fl_away": 12.8,
            "exp_sv_home": 2.8, "exp_sv_away": 3.5,
        }
        
        if resp.status_code == 200:
            data = resp.json().get("event", {})
            return {
                "home": data.get("homeTeam", {}).get("name", "Local"),
                "away": data.get("awayTeam", {}).get("name", "Visitante"),
                **default_stats
            }
        else:
            if "/match/" in url:
                slug = url.split("/match/")[1].split("/")[0]
                partes = slug.replace("-", " ").title().split(" ")
                mitad = len(partes) // 2
                return {
                    "home": " ".join(partes[:mitad]) if mitad > 0 else "Local",
                    "away": " ".join(partes[mitad:]) if mitad > 0 else "Visitante",
                    **default_stats
                }
    except Exception as e:
        print(f"Error consultando SofaScore: {e}")
    return None

# =========================================================
# SIMULACIÓN MONTE CARLO (MERCADOS EXTENDIDOS)
# =========================================================
def run_monte_carlo_analysis(match, n_simulations=10000):
    exp_g_h = match.get("exp_g_home", 1.6)
    exp_g_a = match.get("exp_g_away", 1.2)
    exp_c_h = match.get("exp_c_home", 5.2)
    exp_c_a = match.get("exp_c_away", 4.1)
    exp_card_h = match.get("exp_card_home", 2.1)
    exp_card_a = match.get("exp_card_away", 2.4)
    exp_off_h = match.get("exp_off_home", 1.8)
    exp_off_a = match.get("exp_off_away", 1.5)
    exp_sot_h = match.get("exp_sot_home", 4.5)
    exp_sot_a = match.get("exp_sot_away", 3.8)
    exp_st_h = match.get("exp_st_home", 12.5)
    exp_st_a = match.get("exp_st_away", 10.2)
    exp_fl_h = match.get("exp_fl_home", 11.5)
    exp_fl_a = match.get("exp_fl_away", 12.8)
    exp_sv_h = match.get("exp_sv_home", 2.8)
    exp_sv_a = match.get("exp_sv_away", 3.5)

    # 1. Goles
    gh = np.random.poisson(exp_g_h, n_simulations)
    ga = np.random.poisson(exp_g_a, n_simulations)
    gh_1t = np.random.binomial(gh, 0.45)
    ga_1t = np.random.binomial(ga, 0.45)
    gh_2t = gh - gh_1t
    ga_2t = ga - ga_1t

    # 2. Córners y Tarjetas
    ch = np.random.poisson(exp_c_h, n_simulations)
    ca = np.random.poisson(exp_c_a, n_simulations)
    card_h = np.random.poisson(exp_card_h, n_simulations)
    card_a = np.random.poisson(exp_card_a, n_simulations)

    # 3. Fueras de Lugar (Offsides)
    off_h = np.random.poisson(exp_off_h, n_simulations)
    off_a = np.random.poisson(exp_off_a, n_simulations)

    # 4. Disparos a Puerta (Shots on Target)
    sot_h = np.random.poisson(exp_sot_h, n_simulations)
    sot_a = np.random.poisson(exp_sot_a, n_simulations)

    # 5. Disparos Totales
    st_h = np.random.poisson(exp_st_h, n_simulations)
    st_a = np.random.poisson(exp_st_a, n_simulations)

    # 6. Faltas
    fl_h = np.random.poisson(exp_fl_h, n_simulations)
    fl_a = np.random.poisson(exp_fl_a, n_simulations)

    # 7. Atajadas de Portero
    sv_h = np.random.poisson(exp_sv_h, n_simulations)
    sv_a = np.random.poisson(exp_sv_a, n_simulations)

    p_first_h = exp_g_h / (exp_g_h + exp_g_a) if (exp_g_h + exp_g_a) > 0 else 0.5
    has_goals = (gh + ga) > 0
    first_scorer_rand = np.random.binomial(1, p_first_h, n_simulations)
    first_home = has_goals & (first_scorer_rand == 1)
    first_away = has_goals & (first_scorer_rand == 0)
    no_goals = ~has_goals

    sim = {
        "ml_home": np.mean(gh > ga) * 100,
        "ml_draw": np.mean(gh == ga) * 100,
        "ml_away": np.mean(ga > gh) * 100,
        "dc_1x": np.mean(gh >= ga) * 100,
        "dc_x2": np.mean(ga >= gh) * 100,
        "dc_12": np.mean(gh != ga) * 100,

        "btts_yes": np.mean((gh > 0) & (ga > 0)) * 100,
        "btts_no": np.mean((gh == 0) | (ga == 0)) * 100,
        "goles_over_15": np.mean((gh + ga) > 1.5) * 100,
        "goles_under_15": np.mean((gh + ga) <= 1.5) * 100,
        "goles_over_25": np.mean((gh + ga) > 2.5) * 100,
        "goles_under_25": np.mean((gh + ga) <= 2.5) * 100,
        "goles_over_35": np.mean((gh + ga) > 3.5) * 100,
        "goles_under_35": np.mean((gh + ga) <= 3.5) * 100,

        "goles_1t_over_05": np.mean((gh_1t + ga_1t) > 0.5) * 100,
        "goles_1t_under_05": np.mean((gh_1t + ga_1t) <= 0.5) * 100,
        "goles_1t_over_15": np.mean((gh_1t + ga_1t) > 1.5) * 100,
        "goles_1t_under_15": np.mean((gh_1t + ga_1t) <= 1.5) * 100,
        "first_home": np.mean(first_home) * 100,
        "first_away": np.mean(first_away) * 100,
        "first_none": np.mean(no_goals) * 100,
        "win_1t_home": np.mean(gh_1t > ga_1t) * 100,
        "win_1t_draw": np.mean(gh_1t == ga_1t) * 100,
        "win_1t_away": np.mean(ga_1t > gh_1t) * 100,
        "win_2t_home": np.mean(gh_2t > ga_2t) * 100,
        "win_2t_draw": np.mean(gh_2t == ga_2t) * 100,
        "win_2t_away": np.mean(ga_2t > gh_2t) * 100,

        "corners_over_85": np.mean((ch + ca) > 8.5) * 100,
        "corners_under_85": np.mean((ch + ca) <= 8.5) * 100,
        "corners_over_95": np.mean((ch + ca) > 9.5) * 100,
        "corners_under_95": np.mean((ch + ca) <= 9.5) * 100,
        "corners_home_over_45": np.mean(ch > 4.5) * 100,
        "corners_home_under_45": np.mean(ch <= 4.5) * 100,
        "corners_away_over_35": np.mean(ca > 3.5) * 100,
        "corners_away_under_35": np.mean(ca <= 3.5) * 100,

        "cards_over_35": np.mean((card_h + card_a) > 3.5) * 100,
        "cards_under_35": np.mean((card_h + card_a) <= 3.5) * 100,
        "cards_over_45": np.mean((card_h + card_a) > 4.5) * 100,
        "cards_under_45": np.mean((card_h + card_a) <= 4.5) * 100,
        "cards_home_over_15": np.mean(card_h > 1.5) * 100,
        "cards_home_under_15": np.mean(card_h <= 1.5) * 100,
        "cards_away_over_15": np.mean(card_a > 1.5) * 100,
        "cards_away_under_15": np.mean(card_a <= 1.5) * 100,

        "off_over_25": np.mean((off_h + off_a) > 2.5) * 100,
        "off_under_25": np.mean((off_h + off_a) <= 2.5) * 100,
        "off_over_35": np.mean((off_h + off_a) > 3.5) * 100,
        "off_under_35": np.mean((off_h + off_a) <= 3.5) * 100,
        "off_home_over_15": np.mean(off_h > 1.5) * 100,
        "off_home_under_15": np.mean(off_h <= 1.5) * 100,
        "off_away_over_15": np.mean(off_a > 1.5) * 100,
        "off_away_under_15": np.mean(off_a <= 1.5) * 100,

        "sot_over_75": np.mean((sot_h + sot_a) > 7.5) * 100,
        "sot_under_75": np.mean((sot_h + sot_a) <= 7.5) * 100,
        "sot_over_85": np.mean((sot_h + sot_a) > 8.5) * 100,
        "sot_under_85": np.mean((sot_h + sot_a) <= 8.5) * 100,
        "sot_home_over_35": np.mean(sot_h > 3.5) * 100,
        "sot_home_under_35": np.mean(sot_h <= 3.5) * 100,
        "sot_away_over_25": np.mean(sot_a > 2.5) * 100,
        "sot_away_under_25": np.mean(sot_a <= 2.5) * 100,

        "st_over_215": np.mean((st_h + st_a) > 21.5) * 100,
        "st_under_215": np.mean((st_h + st_a) <= 21.5) * 100,
        "st_over_235": np.mean((st_h + st_a) > 23.5) * 100,
        "st_under_235": np.mean((st_h + st_a) <= 23.5) * 100,
        "st_home_over_115": np.mean(st_h > 11.5) * 100,
        "st_home_under_115": np.mean(st_h <= 11.5) * 100,
        "st_away_over_95": np.mean(st_a > 9.5) * 100,
        "st_away_under_95": np.mean(st_a <= 9.5) * 100,

        "fl_over_225": np.mean((fl_h + fl_a) > 22.5) * 100,
        "fl_under_225": np.mean((fl_h + fl_a) <= 22.5) * 100,
        "fl_over_245": np.mean((fl_h + fl_a) > 24.5) * 100,
        "fl_under_245": np.mean((fl_h + fl_a) <= 24.5) * 100,
        "fl_home_over_105": np.mean(fl_h > 10.5) * 100,
        "fl_home_under_105": np.mean(fl_h <= 10.5) * 100,
        "fl_away_over_115": np.mean(fl_a > 11.5) * 100,
        "fl_away_under_115": np.mean(fl_a <= 11.5) * 100,

        "sv_over_55": np.mean((sv_h + sv_a) > 5.5) * 100,
        "sv_under_55": np.mean((sv_h + sv_a) <= 5.5) * 100,
        "sv_over_65": np.mean((sv_h + sv_a) > 6.5) * 100,
        "sv_under_65": np.mean((sv_h + sv_a) <= 6.5) * 100,
        "sv_home_over_25": np.mean(sv_h > 2.5) * 100,
        "sv_home_under_25": np.mean(sv_h <= 2.5) * 100,
        "sv_away_over_25": np.mean(sv_a > 2.5) * 100,
        "sv_away_under_25": np.mean(sv_a <= 2.5) * 100,
    }
    return sim

def generar_reporte_partido(match, sim):
    home = match.get('home', 'Local')
    away = match.get('away', 'Visitante')

    mercados_evaluados = [
        (f"Gana {home}", sim["ml_home"]),
        ("Empate", sim["ml_draw"]),
        (f"Gana {away}", sim["ml_away"]),
        (f"Doble Oportunidad 1X ({home} o Empate)", sim["dc_1x"]),
        (f"Doble Oportunidad X2 ({away} o Empate)", sim["dc_x2"]),
        ("Doble Oportunidad 12 (Sin Empate)", sim["dc_12"]),
        ("Ambos anotan - Sí", sim["btts_yes"]),
        ("Ambos anotan - No", sim["btts_no"]),
        ("Over 1.5 goles partido", sim["goles_over_15"]),
        ("Under 1.5 goles partido", sim["goles_under_15"]),
        ("Over 2.5 goles partido", sim["goles_over_25"]),
        ("Under 2.5 goles partido", sim["goles_under_25"]),
        ("Over 3.5 goles partido", sim["goles_over_35"]),
        ("Under 3.5 goles partido", sim["goles_under_35"]),
        ("Over 0.5 goles 1er Tiempo", sim["goles_1t_over_05"]),
        ("Under 0.5 goles 1er Tiempo", sim["goles_1t_under_05"]),
        ("Over 1.5 goles 1er Tiempo", sim["goles_1t_over_15"]),
        ("Under 1.5 goles 1er Tiempo", sim["goles_1t_under_15"]),
        (f"Primer equipo en anotar: {home}", sim["first_home"]),
        (f"Primer equipo en anotar: {away}", sim["first_away"]),
        ("Sin goles en el partido", sim["first_none"]),
        (f"Gana 1er Tiempo: {home}", sim["win_1t_home"]),
        ("Empate 1er Tiempo", sim["win_1t_draw"]),
        (f"Gana 1er Tiempo: {away}", sim["win_1t_away"]),
        (f"Gana 2do Tiempo: {home}", sim["win_2t_home"]),
        ("Empate 2do Tiempo", sim["win_2t_draw"]),
        (f"Gana 2do Tiempo: {away}", sim["win_2t_away"]),
        ("Over 8.5 córners partido", sim["corners_over_85"]),
        ("Under 8.5 córners partido", sim["corners_under_85"]),
        ("Over 9.5 córners partido", sim["corners_over_95"]),
        ("Under 9.5 córners partido", sim["corners_under_95"]),
        (f"Over 4.5 córners {home}", sim["corners_home_over_45"]),
        (f"Under 4.5 córners {home}", sim["corners_home_under_45"]),
        (f"Over 3.5 córners {away}", sim["corners_away_over_35"]),
        (f"Under 3.5 córners {away}", sim["corners_away_under_35"]),
        ("Over 3.5 tarjetas partido", sim["cards_over_35"]),
        ("Under 3.5 tarjetas partido", sim["cards_under_35"]),
        ("Over 4.5 tarjetas partido", sim["cards_over_45"]),
        ("Under 4.5 tarjetas partido", sim["cards_under_45"]),
        (f"Over 1.5 tarjetas {home}", sim["cards_home_over_15"]),
        (f"Under 1.5 tarjetas {home}", sim["cards_home_under_15"]),
        (f"Over 1.5 tarjetas {away}", sim["cards_away_over_15"]),
        (f"Under 1.5 tarjetas {away}", sim["cards_away_under_15"]),
        ("Over 2.5 fueras de lugar", sim["off_over_25"]),
        ("Under 2.5 fueras de lugar", sim["off_under_25"]),
        ("Over 3.5 fueras de lugar", sim["off_over_35"]),
        ("Under 3.5 fueras de lugar", sim["off_under_35"]),
        (f"Over 1.5 fueras de lugar {home}", sim["off_home_over_15"]),
        (f"Under 1.5 fueras de lugar {home}", sim["off_home_under_15"]),
        (f"Over 1.5 fueras de lugar {away}", sim["off_away_over_15"]),
        (f"Under 1.5 fueras de lugar {away}", sim["off_away_under_15"]),
        ("Over 7.5 disparos a puerta", sim["sot_over_75"]),
        ("Under 7.5 disparos a puerta", sim["sot_under_75"]),
        ("Over 8.5 disparos a puerta", sim["sot_over_85"]),
        ("Under 8.5 disparos a puerta", sim["sot_under_85"]),
        (f"Over 3.5 disparos a puerta {home}", sim["sot_home_over_35"]),
        (f"Under 3.5 disparos a puerta {home}", sim["sot_home_under_35"]),
        (f"Over 2.5 disparos a puerta {away}", sim["sot_away_over_25"]),
        (f"Under 2.5 disparos a puerta {away}", sim["sot_away_under_25"]),
        ("Over 21.5 disparos totales", sim["st_over_215"]),
        ("Under 21.5 disparos totales", sim["st_under_215"]),
        ("Over 23.5 disparos totales", sim["st_over_235"]),
        ("Under 23.5 disparos totales", sim["st_under_235"]),
        (f"Over 11.5 disparos totales {home}", sim["st_home_over_115"]),
        (f"Under 11.5 disparos totales {home}", sim["st_home_under_115"]),
        (f"Over 9.5 disparos totales {away}", sim["st_away_over_95"]),
        (f"Under 9.5 disparos totales {away}", sim["st_away_under_95"]),
        ("Over 22.5 faltas partido", sim["fl_over_225"]),
        ("Under 22.5 faltas partido", sim["fl_under_225"]),
        ("Over 24.5 faltas partido", sim["fl_over_245"]),
        ("Under 24.5 faltas partido", sim["fl_under_245"]),
        (f"Over 10.5 faltas {home}", sim["fl_home_over_105"]),
        (f"Under 10.5 faltas {home}", sim["fl_home_under_105"]),
        (f"Over 11.5 faltas {away}", sim["fl_away_over_115"]),
        (f"Under 11.5 faltas {away}", sim["fl_away_under_115"]),
        ("Over 5.5 atajadas porteros", sim["sv_over_55"]),
        ("Under 5.5 atajadas porteros", sim["sv_under_55"]),
        ("Over 6.5 atajadas porteros", sim["sv_over_65"]),
        ("Under 6.5 atajadas porteros", sim["sv_under_65"]),
        (f"Over 2.5 atajadas portero {home}", sim["sv_home_over_25"]),
        (f"Under 2.5 atajadas portero {home}", sim["sv_home_under_25"]),
        (f"Over 2.5 atajadas portero {away}", sim["sv_away_over_25"]),
        (f"Under 2.5 atajadas portero {away}", sim["sv_away_under_25"]),
    ]

    candidatos_85 = [(nombre, prob) for nombre, prob in mercados_evaluados if prob >= 85.0]

    if candidatos_85:
        candidatos_85.sort(key=lambda x: x[1], reverse=True)
        top_picks = [f"• {nombre} ({prob:.0f}%)" for nombre, prob in candidatos_85[:4]]
        apuesta_derecha_txt = "\n".join(top_picks)
    else:
        apuesta_derecha_txt = "Sin selecciones directas ≥85%"

    reporte_texto = f"""⚽ ANÁLISIS DE MATCH: {home} vs {away}

💵 MONEYLINE & DOBLE CHANCE
* {home}: {sim['ml_home']:.0f}% | Empate: {sim['ml_draw']:.0f}% | {away}: {sim['ml_away']:.0f}%
* Doble Chance: 1X ({sim['dc_1x']:.0f}%) | X2 ({sim['dc_x2']:.0f}%) | 12 ({sim['dc_12']:.0f}%)

⚽ GOLES & BTTS
* Ambos Anotan: Sí ({sim['btts_yes']:.0f}%) | No ({sim['btts_no']:.0f}%)
* Over/Under 1.5 Goles: Over ({sim['goles_over_15']:.0f}%) | Under ({sim['goles_under_15']:.0f}%)
* Over/Under 2.5 Goles: Over ({sim['goles_over_25']:.0f}%) | Under ({sim['goles_under_25']:.0f}%)
* Over/Under 3.5 Goles: Over ({sim['goles_over_35']:.0f}%) | Under ({sim['goles_under_35']:.0f}%)

⏱️ PRIMER TIEMPO & GANADOR DE MITAD
* Goles 1T (O/U 0.5): Over ({sim['goles_1t_over_05']:.0f}%) | Under ({sim['goles_1t_under_05']:.0f}%)
* Goles 1T (O/U 1.5): Over ({sim['goles_1t_over_15']:.0f}%) | Under ({sim['goles_1t_under_15']:.0f}%)
* Gana 1er Tiempo: {home} ({sim['win_1t_home']:.0f}%) | X ({sim['win_1t_draw']:.0f}%) | {away} ({sim['win_1t_away']:.0f}%)
* Gana 2do Tiempo: {home} ({sim['win_2t_home']:.0f}%) | X ({sim['win_2t_draw']:.0f}%) | {away} ({sim['win_2t_away']:.0f}%)

🎯 QUIÉN ANOTA PRIMERO
* {home}: {sim['first_home']:.0f}% | {away}: {sim['first_away']:.0f}% | Sin goles: {sim['first_none']:.0f}%

🚩 CÓRNERS (PARTIDO E INDIVIDUAL)
* Totales: Over 8.5 ({sim['corners_over_85']:.0f}%) | Over 9.5 ({sim['corners_over_95']:.0f}%)
* {home}: Over 4.5 ({sim['corners_home_over_45']:.0f}%) | {away}: Over 3.5 ({sim['corners_away_over_35']:.0f}%)

🟨 TARJETAS (PARTIDO E INDIVIDUAL)
* Totales: Over 3.5 ({sim['cards_over_35']:.0f}%) | Over 4.5 ({sim['cards_over_45']:.0f}%)
* {home}: Over 1.5 ({sim['cards_home_over_15']:.0f}%) | {away}: Over 1.5 ({sim['cards_away_over_15']:.0f}%)

🚩 FUERA DE LUGAR (OFFSIDES)
* Totales: Over 2.5 ({sim['off_over_25']:.0f}%) | Over 3.5 ({sim['off_over_35']:.0f}%)
* {home}: Over 1.5 ({sim['off_home_over_15']:.0f}%) | {away}: Over 1.5 ({sim['off_away_over_15']:.0f}%)

🎯 DISPAROS A PUERTA (SOT)
* Totales: Over 7.5 ({sim['sot_over_75']:.0f}%) | Over 8.5 ({sim['sot_over_85']:.0f}%)
* {home}: Over 3.5 ({sim['sot_home_over_35']:.0f}%) | {away}: Over 2.5 ({sim['sot_away_over_25']:.0f}%)

⚽ DISPAROS TOTALES
* Totales: Over 21.5 ({sim['st_over_215']:.0f}%) | Over 23.5 ({sim['st_over_235']:.0f}%)
* {home}: Over 11.5 ({sim['st_home_over_115']:.0f}%) | {away}: Over 9.5 ({sim['st_away_over_95']:.0f}%)

⚠️ FALTAS COMETIDAS
* Totales: Over 22.5 ({sim['fl_over_225']:.0f}%) | Over 24.5 ({sim['fl_over_245']:.0f}%)
* {home}: Over 10.5 ({sim['fl_home_over_105']:.0f}%) | {away}: Over 11.5 ({sim['fl_away_under_115']:.0f}%)

🧤 ATAJADAS DE PORTERO
* Totales: Over 5.5 ({sim['sv_over_55']:.0f}%) | Over 6.5 ({sim['sv_over_65']:.0f}%)
* {home}: Over 2.5 ({sim['sv_home_over_25']:.0f}%) | {away}: Over 2.5 ({sim['sv_away_over_25']:.0f}%)

🔥 SELECCIONES RECOMENDADAS (≥85%):
{apuesta_derecha_txt}"""
    return reporte_texto

# =========================================================
# TAREA AUTOMÁTICA DIARIA (BARRIDO NOCTURNO 21:00 PM)
# =========================================================
def ejecutar_analisis_diario_21pm():
    manana = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    send_telegram_message(f"🚀 Iniciando barrido diario para mañana ({manana})...")

    # Corregido: v1 en lugar de v3 para la API de SofaScore
    url_api = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{manana}"
    try:
        scraper = get_scraper()
        resp = scraper.get(url_api, timeout=15)
        
        if resp.status_code == 200:
            events = resp.json().get("events", [])
            if not events:
                send_telegram_message("⚠️ No se encontraron partidos programados para mañana.")
                return

            eventos_filtrados = [
                ev for ev in events 
                if not LIGAS_OBJETIVO_IDS or ev.get("tournament", {}).get("uniqueTournament", {}).get("id") in LIGAS_OBJETIVO_IDS
            ]

            total_partidos = len(eventos_filtrados)
            send_telegram_message(f"📊 Total de partidos a procesar: {total_partidos}. Se enviarán 2 partidos por mensaje cada 90 segundos.")

            for i in range(0, total_partidos, 2):
                lote = eventos_filtrados[i:i+2]
                reportes_lote = []

                for event in lote:
                    match_info = {
                        "home": event.get("homeTeam", {}).get("name", "Local"),
                        "away": event.get("awayTeam", {}).get("name", "Visitante"),
                        "exp_g_home": 1.6, "exp_g_away": 1.2,
                        "exp_c_home": 5.2, "exp_c_away": 4.1,
                        "exp_card_home": 2.1, "exp_card_away": 2.4,
                        "exp_off_home": 1.8, "exp_off_away": 1.5,
                        "exp_sot_home": 4.5, "exp_sot_away": 3.8,
                        "exp_st_home": 12.5, "exp_st_away": 10.2,
                        "exp_fl_home": 11.5, "exp_fl_away": 12.8,
                        "exp_sv_home": 2.8, "exp_sv_away": 3.5,
                    }
                    sim = run_monte_carlo_analysis(match_info)
                    reportes_lote.append(generar_reporte_partido(match_info, sim))

                mensaje_unificado = "\n\n====================\n\n".join(reportes_lote)
                send_telegram_message(mensaje_unificado)

                if i + 2 < total_partidos:
                    time.sleep(90)

        else:
            send_telegram_message(f"❌ Error al consultar SofaScore (Código HTTP: {resp.status_code}).")
    except Exception as e:
        print(f"Error en tarea nocturna: {e}")
        send_telegram_message(f"❌ Error durante el barrido diario: {e}")

# =========================================================
# PROGRAMADOR DE TAREAS SCHEDULER (9:00 PM MEXICO CITY)
# =========================================================
scheduler = BackgroundScheduler(timezone="America/Mexico_City")
scheduler.add_job(func=ejecutar_analisis_diario_21pm, trigger="cron", hour=21, minute=0)
scheduler.start()

# =========================================================
# PROCESAMIENTO EN SEGUNDO PLANO DE ENLACES INDIVIDUALES
# =========================================================
def procesar_partido_background(url_raw, chat_id):
    try:
        url = url_raw.strip()
        partido = obtener_partido_por_url(url)
        if not partido:
            send_telegram_message("❌ No se pudieron obtener los datos del enlace de SofaScore.", chat_id=chat_id)
            return

        sim = run_monte_carlo_analysis(partido)
        reporte_texto = generar_reporte_partido(partido, sim)
        send_telegram_message(reporte_texto, chat_id=chat_id)

    except Exception as e:
        print(f"Error en procesamiento individual: {e}")
        send_telegram_message(f"⚠️ Error al procesar el partido: {str(e)}", chat_id=chat_id)

# =========================================================
# RUTAS DE LA APLICACIÓN WEB (FLASK & TELEGRAM WEBHOOK)
# =========================================================
def procesar_webhook_telegram(req):
    try:
        data = req.get_json(force=True, silent=True)
        if not data or "message" not in data:
            return "OK", 200

        message = data["message"]
        chat_id = message["chat"]["id"]
        text = (message.get("text") or message.get("caption") or "").strip()

        if "sofascore.com" in text:
            send_telegram_message("🔍 Analizando partido individual...\nEjecutando simulaciones de Monte Carlo...", chat_id=chat_id)
            
            words = text.split()
            url = next((w.strip() for w in words if "sofascore.com" in w), None)

            if url:
                # Corregido: threading.Thread en lugar de multiprocessing.Process
                t = threading.Thread(target=procesar_partido_background, args=(url, chat_id), daemon=True)
                t.start()
            else:
                send_telegram_message("❌ No se pudo extraer la URL del mensaje.", chat_id=chat_id)

    except Exception as e:
        print(f"Error en Webhook: {e}")

    return "OK", 200

@app.route("/", methods=["GET", "HEAD", "POST"])
def index():
    if request.method == "POST":
        return procesar_webhook_telegram(request)
    return "Bot Monte Carlo activo y en espera.", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    return procesar_webhook_telegram(request)

@app.route("/run", methods=["GET", "POST"])
@app.route("/run-daily", methods=["GET", "POST"])
def manual_trigger():
    try:
        # Corregido: threading.Thread en lugar de multiprocessing.Process
        t = threading.Thread(target=ejecutar_analisis_diario_21pm, daemon=True)
        t.start()
        return "Análisis ejecutado manualmente y enviado a Telegram.", 200
    except Exception as e:
        return f"Error al ejecutar: {str(e)}", 500

# =========================================================
# PUNTO DE ENTRADA PRINCIPAL
# =========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
