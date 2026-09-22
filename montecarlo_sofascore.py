import os
import json
import logging
from datetime import datetime, timedelta
import numpy as np
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from curl_cffi import requests as cffi_requests

# Configuración de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(_name_)

# Configuración de Headers para SofaScore
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "/",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

SIMULATIONS = 100_000

def simulate_poisson(lambda_param, size=SIMULATIONS):
    """Genera n simulaciones de Poisson basadas en una media esperada (lambda)."""
    if lambda_param <= 0:
        lambda_param = 0.1
    return np.random.poisson(lambda_param, size)

def run_monte_carlo_analysis(match_data):
    """
    Ejecuta 100,000 simulaciones de Monte Carlo para todos los mercados del partido.
    """
    home = match_data.get('home_team', 'Local')
    away = match_data.get('away_team', 'Visitante')

    # Medias esperadas (Lambdas) extraídas o estimadas
    exp_goals_h = match_data.get('exp_goals_home', 1.4)
    exp_goals_a = match_data.get('exp_goals_away', 1.1)
    
    exp_corners_h = match_data.get('exp_corners_home', 5.2)
    exp_corners_a = match_data.get('exp_corners_away', 4.3)
    
    exp_cards_h = match_data.get('exp_cards_home', 2.1)
    exp_cards_a = match_data.get('exp_cards_away', 2.4)
    
    exp_offsides_h = match_data.get('exp_offsides_home', 1.8)
    exp_offsides_a = match_data.get('exp_offsides_away', 1.6)

    exp_shots_h = match_data.get('exp_shots_home', 4.8)
    exp_shots_a = match_data.get('exp_shots_away', 3.9)

    # 1. SIMULACIONES MONTE CARLO (100,000 corridas)
    sim_goals_h = simulate_poisson(exp_goals_h)
    sim_goals_a = simulate_poisson(exp_goals_a)
    sim_goals_total = sim_goals_h + sim_goals_a

    # 1er Tiempo (aproximación ~45% de la media de goles)
    sim_ht_goals_h = simulate_poisson(exp_goals_h * 0.45)
    sim_ht_goals_a = simulate_poisson(exp_goals_a * 0.45)
    sim_ht_goals_total = sim_ht_goals_h + sim_ht_goals_a

    # Córners
    sim_corners_h = simulate_poisson(exp_corners_h)
    sim_corners_a = simulate_poisson(exp_corners_a)
    sim_corners_total = sim_corners_h + sim_corners_a

    # Tarjetas
    sim_cards_h = simulate_poisson(exp_cards_h)
    sim_cards_a = simulate_poisson(exp_cards_a)
    sim_cards_total = sim_cards_h + sim_cards_a

    # Fueras de Lugar y Tiros a Puerta
    sim_offsides_total = simulate_poisson(exp_offsides_h) + simulate_poisson(exp_offsides_a)
    sim_shots_total = simulate_poisson(exp_shots_h) + simulate_poisson(exp_shots_a)

    # 2. PROBABILIDADES Y MERCADOS MATRIZ OVER / UNDER
    markets = {}

    # --- GOLES PARTIDO ---
    for line in [1.5, 2.5, 3.5]:
        over_pct = float(np.mean(sim_goals_total > line) * 100)
        under_pct = 100.0 - over_pct
        markets[f"Goles Partido Over {line}"] = round(over_pct, 2)
        markets[f"Goles Partido Under {line}"] = round(under_pct, 2)

    # --- GOLES 1ST HALF ---
    for line in [0.5, 1.5]:
        over_pct = float(np.mean(sim_ht_goals_total > line) * 100)
        under_pct = 100.0 - over_pct
        markets[f"Goles 1er Tiempo Over {line}"] = round(over_pct, 2)
        markets[f"Goles 1er Tiempo Under {line}"] = round(under_pct, 2)

    # --- GOLES INDIVIDUALES ---
    markets[f"Goles {home} Over 1.5"] = round(float(np.mean(sim_goals_h > 1.5) * 100), 2)
    markets[f"Goles {home} Under 1.5"] = round(100.0 - markets[f"Goles {home} Over 1.5"], 2)
    markets[f"Goles {away} Over 1.5"] = round(float(np.mean(sim_goals_a > 1.5) * 100), 2)
    markets[f"Goles {away} Under 1.5"] = round(100.0 - markets[f"Goles {away} Over 1.5"], 2)

    # --- CÓRNERS PARTIDO & INDIVIDUAL ---
    for line in [8.5, 9.5, 10.5]:
        over_pct = float(np.mean(sim_corners_total > line) * 100)
        markets[f"Córners Partido Over {line}"] = round(over_pct, 2)
        markets[f"Córners Partido Under {line}"] = round(100.0 - over_pct, 2)

    markets[f"Córners {home} Over 4.5"] = round(float(np.mean(sim_corners_h > 4.5) * 100), 2)
    markets[f"Córners {home} Under 4.5"] = round(100.0 - markets[f"Córners {home} Over 4.5"], 2)
    markets[f"Córners {away} Over 4.5"] = round(float(np.mean(sim_corners_a > 4.5) * 100), 2)
    markets[f"Córners {away} Under 4.5"] = round(100.0 - markets[f"Córners {away} Over 4.5"], 2)

    # --- TARJETAS PARTIDO & INDIVIDUAL ---
    for line in [3.5, 4.5, 5.5]:
        over_pct = float(np.mean(sim_cards_total > line) * 100)
        markets[f"Tarjetas Partido Over {line}"] = round(over_pct, 2)
        markets[f"Tarjetas Partido Under {line}"] = round(100.0 - over_pct, 2)

    markets[f"Tarjetas {home} Over 1.5"] = round(float(np.mean(sim_cards_h > 1.5) * 100), 2)
    markets[f"Tarjetas {home} Under 1.5"] = round(100.0 - markets[f"Tarjetas {home} Over 1.5"], 2)

    # --- AMBOS ANOTAN (BTTS) ---
    btts_yes = float(np.mean((sim_goals_h > 0) & (sim_goals_a > 0)) * 100)
    markets["Ambos Anotan SÍ"] = round(btts_yes, 2)
    markets["Ambos Anotan NO"] = round(100.0 - btts_yes, 2)

    # --- MONEYLINE (1X2) & DOBLE CHANCE ---
    p_home_win = float(np.mean(sim_goals_h > sim_goals_a) * 100)
    p_draw = float(np.mean(sim_goals_h == sim_goals_a) * 100)
    p_away_win = float(np.mean(sim_goals_a > sim_goals_h) * 100)

    markets[f"Victoria {home} (1)"] = round(p_home_win, 2)
    markets["Empate (X)"] = round(p_draw, 2)
    markets[f"Victoria {away} (2)"] = round(p_away_win, 2)

    markets[f"Doble Oportunidad 1X ({home} o Empate)"] = round(p_home_win + p_draw, 2)
    markets[f"Doble Oportunidad X2 ({away} o Empate)"] = round(p_away_win + p_draw, 2)
    markets["Doble Oportunidad 12 (Sin Empate)"] = round(p_home_win + p_away_win, 2)

    # --- PRIMERO EN ANOTAR ---
    markets[f"Anota Primero {home}"] = round(float((exp_goals_h / (exp_goals_h + exp_goals_a)) * 100), 2)
    markets[f"Anota Primero {away}"] = round(100.0 - markets[f"Anota Primero {home}"], 2)

    # --- TIROS A PUERTA & FUERAS DE LUGAR ---
    markets["Tiros a Puerta Over 8.5"] = round(float(np.mean(sim_shots_total > 8.5) * 100), 2)
    markets["Fueras de Lugar Over 3.5"] = round(float(np.mean(sim_offsides_total > 3.5) * 100), 2)

    return {
        "match": f"{home} vs {away}",
        "league": match_data.get('league', 'General'),
        "markets": markets
    }

def analyze_all_matches():
    """
    Función principal que consulta los partidos de mañana en SofaScore,
    corre Monte Carlo para cada uno y selecciona la Apuesta Directa del Día.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"--- INICIANDO ANÁLISIS AUTOMÁTICO DE MATCHES PARA: {tomorrow} ---")

    # [SofaScore Mock/API Fetch Step]
    # Reemplazable dinámicamente con las peticiones directas a SofaScore por API/ID
    sample_matches = [
        {
            "home_team": "Real Madrid", "away_team": "Barcelona", "league": "La Liga",
            "exp_goals_home": 1.8, "exp_goals_away": 1.5,
            "exp_corners_home": 6.1, "exp_corners_away": 4.8,
            "exp_cards_home": 2.5, "exp_cards_away": 3.1
        },
        {
            "home_team": "Manchester City", "away_team": "Arsenal", "league": "Premier League",
            "exp_goals_home": 2.1, "exp_goals_away": 1.1,
            "exp_corners_home": 6.8, "exp_corners_away": 3.9,
            "exp_cards_home": 1.8, "exp_cards_away": 2.2
        }
    ]

    all_results = []
    best_pick = {"market": None, "prob": 0.0, "match": None}

    for match in sample_matches:
        analysis = run_monte_carlo_analysis(match)
        all_results.append(analysis)

        # Buscar el Pick Estrella (Apuesta Directa >85%)
        for m_name, prob in analysis["markets"].items():
            if prob > best_pick["prob"] and prob >= 85.0:
                best_pick = {
                    "match": analysis["match"],
                    "market": m_name,
                    "prob": prob
                }

    report = {
        "date": tomorrow,
        "matches_analyzed": len(all_results),
        "results": all_results,
        "direct_bet_pick_of_the_day": best_pick if best_pick["market"] else "Sin picks directos mayores a 85% hoy."
    }

    logging.info(f"Análisis finalizado con éxito. Pick Estrella: {best_pick}")
    return report

# Scheduler de APScheduler para correr diario a las 21:00 hrs
scheduler = BackgroundScheduler()
scheduler.add_job(func=analyze_all_matches, trigger="cron", hour=21, minute=0)
scheduler.start()

# --- RUTAS DE FLASK ---

@app.route('/', methods=['GET'])
def health_check():
    """Ruta para UptimeRobot mantenga el bot en vivo 24/7."""
    return "Bot de Análisis Monte Carlo SofaScore - Vivo y Activo", 200

@app.route('/run-now', methods=['GET', 'POST'])
def run_now():
    """Ruta manual para ejecutar el análisis inmediatamente sin esperar a las 9 PM."""
    results = analyze_all_matches()
    return jsonify(results), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
