import os
import logging
from datetime import datetime, timedelta
import numpy as np
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from curl_cffi import requests as cffi_requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(_name_)

# Lista de torneos y ligas a filtrar en SofaScore
TARGET_LEAGUES = [
    "Liga MX", "Liga de Expansión MX", "Liga de Expansion MX",
    "UEFA Champions League", "UEFA Europa League", "UEFA Conference League", "UEFA Nations League",
    "LaLiga", "La Liga", "Copa del Rey",
    "Premier League", "EFL Cup", "Championship", "League One",
    "Serie A", "Coppa Italia", "Copa Italia",
    "Bundesliga", "DFB-Pokal", "Copa de Alemania",
    "Ligue 1", "Coupe de France",
    "Eredivisie", "KNVB Beker",
    "Primeira Liga", "Pro League", "First Division A",
    "Scottish Premiership", "Super Lig", "CONCACAF Nations League"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "/",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/"
}

SIMULATIONS = 100_000

def fetch_sofascore_events(date_str):
    """Obtiene los eventos programados en SofaScore para la fecha solicitada."""
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}"
    try:
        response = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('events', [])
        else:
            logging.error(f"Error al consultar SofaScore API: Status {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Excepción al conectar con SofaScore: {e}")
        return []

def get_team_stats(team_id):
    """
    Obtiene las estadísticas promedio recientes del equipo desde SofaScore.
    Si no hay datos disponibles, retorna estimaciones promedio por defecto.
    """
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/0"
    try:
        res = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=5)
        if res.status_code == 200:
            events = res.json().get('events', [])[:5]
            if events:
                # Extracción rápida de promedios de últimos partidos
                return {
                    "goals": max(0.8, np.mean([e.get('homeScore', {}).get('current', 1) for e in events])),
                    "corners": 5.0,
                    "cards": 2.2,
                    "offsides": 1.8,
                    "shots": 4.5
                }
    except Exception:
        pass
    return {"goals": 1.3, "corners": 4.8, "cards": 2.0, "offsides": 1.5, "shots": 4.2}

def simulate_poisson(lambda_param, size=SIMULATIONS):
    if lambda_param <= 0:
        lambda_param = 0.1
    return np.random.poisson(lambda_param, size)

def run_monte_carlo_analysis(match_info):
    home = match_info['home_team']
    away = match_info['away_team']

    exp_goals_h = match_info.get('exp_goals_home', 1.4)
    exp_goals_a = match_info.get('exp_goals_away', 1.1)
    exp_corners_h = match_info.get('exp_corners_home', 5.0)
    exp_corners_a = match_info.get('exp_corners_away', 4.2)
    exp_cards_h = match_info.get('exp_cards_home', 2.0)
    exp_cards_a = match_info.get('exp_cards_away', 2.3)
    exp_offsides_h = match_info.get('exp_offsides_home', 1.7)
    exp_offsides_a = match_info.get('exp_offsides_away', 1.5)
    exp_shots_h = match_info.get('exp_shots_home', 4.5)
    exp_shots_a = match_info.get('exp_shots_away', 3.8)

    # 100,000 Simulaciones
    sim_goals_h = simulate_poisson(exp_goals_h)
    sim_goals_a = simulate_poisson(exp_goals_a)
    sim_goals_total = sim_goals_h + sim_goals_a

    sim_ht_goals_h = simulate_poisson(exp_goals_h * 0.45)
    sim_ht_goals_a = simulate_poisson(exp_goals_a * 0.45)
    sim_ht_goals_total = sim_ht_goals_h + sim_ht_goals_a

    sim_corners_h = simulate_poisson(exp_corners_h)
    sim_corners_a = simulate_poisson(exp_corners_a)
    sim_corners_total = sim_corners_h + sim_corners_a

    sim_cards_h = simulate_poisson(exp_cards_h)
    sim_cards_a = simulate_poisson(exp_cards_a)
    sim_cards_total = sim_cards_h + sim_cards_a

    sim_offsides_total = simulate_poisson(exp_offsides_h) + simulate_poisson(exp_offsides_a)
    sim_shots_total = simulate_poisson(exp_shots_h) + simulate_poisson(exp_shots_a)

    markets = {}

    # GOLES PARTIDO
    for line in [1.5, 2.5, 3.5]:
        over_pct = float(np.mean(sim_goals_total > line) * 100)
        markets[f"Goles Partido Over {line}"] = round(over_pct, 2)
        markets[f"Goles Partido Under {line}"] = round(100.0 - over_pct, 2)

    # GOLES 1ER TIEMPO
    for line in [0.5, 1.5]:
        over_pct = float(np.mean(sim_ht_goals_total > line) * 100)
        markets[f"Goles 1er Tiempo Over {line}"] = round(over_pct, 2)
        markets[f"Goles 1er Tiempo Under {line}"] = round(100.0 - over_pct, 2)

    # GOLES INDIVIDUALES
    markets[f"Goles {home} Over 1.5"] = round(float(np.mean(sim_goals_h > 1.5) * 100), 2)
    markets[f"Goles {home} Under 1.5"] = round(100.0 - markets[f"Goles {home} Over 1.5"], 2)
    markets[f"Goles {away} Over 1.5"] = round(float(np.mean(sim_goals_a > 1.5) * 100), 2)
    markets[f"Goles {away} Under 1.5"] = round(100.0 - markets[f"Goles {away} Over 1.5"], 2)

    # CÓRNERS PARTIDO & INDIVIDUAL
    for line in [8.5, 9.5, 10.5]:
        over_pct = float(np.mean(sim_corners_total > line) * 100)
        markets[f"Córners Partido Over {line}"] = round(over_pct, 2)
        markets[f"Córners Partido Under {line}"] = round(100.0 - over_pct, 2)

    markets[f"Córners {home} Over 4.5"] = round(float(np.mean(sim_corners_h > 4.5) * 100), 2)
    markets[f"Córners {home} Under 4.5"] = round(100.0 - markets[f"Córners {home} Over 4.5"], 2)
    markets[f"Córners {away} Over 4.5"] = round(float(np.mean(sim_corners_a > 4.5) * 100), 2)
    markets[f"Córners {away} Under 4.5"] = round(100.0 - markets[f"Córners {away} Over 4.5"], 2)

    # TARJETAS PARTIDO & INDIVIDUAL
    for line in [3.5, 4.5, 5.5]:
        over_pct = float(np.mean(sim_cards_total > line) * 100)
        markets[f"Tarjetas Partido Over {line}"] = round(over_pct, 2)
        markets[f"Tarjetas Partido Under {line}"] = round(100.0 - over_pct, 2)

    markets[f"Tarjetas {home} Over 1.5"] = round(float(np.mean(sim_cards_h > 1.5) * 100), 2)
    markets[f"Tarjetas {home} Under 1.5"] = round(100.0 - markets[f"Tarjetas {home} Over 1.5"], 2)

    # AMBOS ANOTAN
    btts_yes = float(np.mean((sim_goals_h > 0) & (sim_goals_a > 0)) * 100)
    markets["Ambos Anotan SÍ"] = round(btts_yes, 2)
    markets["Ambos Anotan NO"] = round(100.0 - btts_yes, 2)

    # MONEYLINE & DOBLE CHANCE
    p_home_win = float(np.mean(sim_goals_h > sim_goals_a) * 100)
    p_draw = float(np.mean(sim_goals_h == sim_goals_a) * 100)
    p_away_win = float(np.mean(sim_goals_a > sim_goals_h) * 100)

    markets[f"Victoria {home} (1)"] = round(p_home_win, 2)
    markets["Empate (X)"] = round(p_draw, 2)
    markets[f"Victoria {away} (2)"] = round(p_away_win, 2)

    markets[f"Doble Oportunidad 1X ({home} o Empate)"] = round(p_home_win + p_draw, 2)
    markets[f"Doble Oportunidad X2 ({away} o Empate)"] = round(p_away_win + p_draw, 2)
    markets["Doble Oportunidad 12 (Sin Empate)"] = round(p_home_win + p_away_win, 2)

    # PRIMERO EN ANOTAR
    total_exp_g = exp_goals_h + exp_goals_a
    p_first_h = (exp_goals_h / total_exp_g * 100) if total_exp_g > 0 else 50.0
    markets[f"Anota Primero {home}"] = round(p_first_h, 2)
    markets[f"Anota Primero {away}"] = round(100.0 - p_first_h, 2)

    # TIROS Y FUERAS DE LUGAR
    markets["Tiros a Puerta Over 8.5"] = round(float(np.mean(sim_shots_total > 8.5) * 100), 2)
    markets["Fueras de Lugar Over 3.5"] = round(float(np.mean(sim_offsides_total > 3.5) * 100), 2)

    return {
        "match": f"{home} vs {away}",
        "league": match_info.get('league', 'General'),
        "markets": markets
    }

def analyze_all_matches():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"--- BARRIDO REAL DE SOFASCORE PARA MAÑANA ({tomorrow}) ---")

    raw_events = fetch_sofascore_events(tomorrow)
    target_matches = []

    for ev in raw_events:
        tournament_name = ev.get('tournament', {}).get('name', '')
        unique_t_name = ev.get('tournament', {}).get('uniqueTournament', {}).get('name', '')

        # Filtrar solo si el torneo está en nuestra lista de interés
        match_league = None
        for t in TARGET_LEAGUES:
            if t.lower() in tournament_name.lower() or t.lower() in unique_t_name.lower():
                match_league = t
                break

        if match_league:
            home_team = ev.get('homeTeam', {}).get('name', 'Local')
            away_team = ev.get('awayTeam', {}).get('name', 'Visitante')
            home_id = ev.get('homeTeam', {}).get('id')
            away_id = ev.get('awayTeam', {}).get('id')

            h_stats = get_team_stats(home_id) if home_id else {}
            a_stats = get_team_stats(away_id) if away_id else {}

            target_matches.append({
                "home_team": home_team,
                "away_team": away_team,
                "league": match_league,
                "exp_goals_home": h_stats.get('goals', 1.4),
                "exp_goals_away": a_stats.get('goals', 1.1),
                "exp_corners_home": h_stats.get('corners', 5.0),
                "exp_corners_away": a_stats.get('corners', 4.2),
                "exp_cards_home": h_stats.get('cards', 2.0),
                "exp_cards_away": a_stats.get('cards', 2.3)
            })

    all_results = []
    best_pick = {"market": None, "prob": 0.0, "match": None}

    for m in target_matches:
        analysis = run_monte_carlo_analysis(m)
        all_results.append(analysis)

        for m_name, prob in analysis["markets"].items():
            if prob > best_pick["prob"] and prob >= 85.0:
                best_pick = {
                    "match": analysis["match"],
                    "market": m_name,
                    "prob": prob
                }

    return {
        "date": tomorrow,
        "matches_analyzed": len(all_results),
        "results": all_results,
        "direct_bet_pick_of_the_day": best_pick if best_pick["market"] else "Sin picks directos mayores a 85% hoy para las ligas seleccionadas."
    }

scheduler = BackgroundScheduler()
scheduler.add_job(func=analyze_all_matches, trigger="cron", hour=21, minute=0)
scheduler.start()

@app.route('/', methods=['GET'])
def health_check():
    return "Bot SofaScore + Montecarlo activo y corriendo 24/7", 200

@app.route('/run-now', methods=['GET', 'POST'])
def run_now():
    results = analyze_all_matches()
    return jsonify(results), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
