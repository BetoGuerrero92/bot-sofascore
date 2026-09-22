import os
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
import numpy as np

app = Flask(__name__)
import requests

TELEGRAM_BOT_TOKEN = "8981343928:AAGkvLxUoHt4tSLP7x20a5QOOTBgnJqruaI"  
TELEGRAM_CHAT_ID = "-5173591171"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def job():
    # Sustituye o vincula aquí tu lógica de extracción de SofaScore
    # Ejemplo de prueba ejecutando la calculadora sobre un partido de muestra:
    match_demo = {
        "exp_g_home": 1.6, "exp_g_away": 1.2,
        "exp_c_home": 5.2, "exp_c_away": 4.1,
        "exp_card_home": 2.1, "exp_card_away": 2.4
    }
    
    # Llama a tu función Monte Carlo existente
    resultados = run_monte_carlo_analysis(match_demo)
    
    # Envía el reporte a Telegram
    mensaje = "⚽ REPORTE DE PRUEBA MONTE CARLO\n\n"
    mensaje += "✅ El bot está conectado correctamente a Telegram.\n"
    mensaje += "🎯 Direct Pick: Local o Empate ( Probabilidad: 78.5% )"
    
    send_telegram_message(mensaje)


@app.route("/")
def health_check():
    try:
        # Ejecuta la función principal que procesa y envía a Telegram
        job() 
        return "Análisis ejecutado y enviado a Telegram correctamente.", 200
    except Exception as e:
        return f"Error durante la ejecución: {str(e)}", 500


def run_monte_carlo_analysis(match, n_simulations=10000):
    exp_goals_home = match.get("exp_g_home", 1.6)
    exp_goals_away = match.get("exp_g_away", 1.2)
    exp_corners_home = match.get("exp_c_home", 5.2)
    exp_corners_away = match.get("exp_c_away", 4.1)
    exp_cards_home = match.get("exp_card_home", 2.1)
    exp_cards_away = match.get("exp_card_away", 2.4)
    exp_offsides_home = match.get("exp_off_home", 2.0)
    exp_offsides_away = match.get("exp_off_away", 1.8)
    exp_saves_home = match.get("exp_sav_home", 3.2)
    exp_saves_away = match.get("exp_sav_away", 3.8)
    exp_sot_home = match.get("exp_sot_home", 5.1)
    exp_sot_away = match.get("exp_sot_away", 4.3)
    exp_shots_home = match.get("exp_sh_home", 13.5)
    exp_shots_away = match.get("exp_sh_away", 11.2)
    exp_fouls_home = match.get("exp_foul_home", 11.8)
    exp_fouls_away = match.get("exp_foul_away", 12.5)

    gh = np.random.poisson(exp_goals_home, n_simulations)
    ga = np.random.poisson(exp_goals_away, n_simulations)

    gh_1t = np.random.binomial(gh, 0.45)
    ga_1t = np.random.binomial(ga, 0.45)
    gh_2t = gh - gh_1t
    ga_2t = ga - ga_1t

    ch = np.random.poisson(exp_corners_home, n_simulations)
    ca = np.random.poisson(exp_corners_away, n_simulations)
    card_h = np.random.poisson(exp_cards_home, n_simulations)
    card_a = np.random.poisson(exp_cards_away, n_simulations)
    off_h = np.random.poisson(exp_offsides_home, n_simulations)
    off_a = np.random.poisson(exp_offsides_away, n_simulations)
    sav_h = np.random.poisson(exp_saves_home, n_simulations)
    sav_a = np.random.poisson(exp_saves_away, n_simulations)
    sot_h = np.random.poisson(exp_sot_home, n_simulations)
    sot_a = np.random.poisson(exp_sot_away, n_simulations)
    sh_h = np.random.poisson(exp_shots_home, n_simulations)
    sh_a = np.random.poisson(exp_shots_away, n_simulations)
    foul_h = np.random.poisson(exp_fouls_home, n_simulations)
    foul_a = np.random.poisson(exp_fouls_away, n_simulations)
    penalties = np.random.binomial(1, 0.22, n_simulations)

    sim = {
        "goles_linea": 2.5,
        "goles_1t_linea": 0.5,
        "corners_totales_over_linea": 8.5,
        "corners_totales_under_linea": 11.5,
        "corners_home_over_linea": 3.5,
        "corners_home_under_linea": 5.5,
        "corners_away_over_linea": 5.5,
        "corners_away_under_linea": 8.5,
        "cards_totales_over_linea": 3.5,
        "cards_totales_under_linea": 5.5,
        "cards_home_over_linea": 1.5,
        "cards_home_under_linea": 2.5,
        "cards_away_over_linea": 1.5,
        "cards_away_under_linea": 2.5,
        "offsides_totales_linea": 3.5,
        "offsides_totales_under_linea": 5.5,
        "offsides_home_linea": 1.5,
        "offsides_home_under_linea": 2.5,
        "offsides_away_linea": 1.5,
        "offsides_away_under_linea": 2.5,
        "saves_totales_linea": 5.5,
        "saves_totales_under_linea": 7.5,
        "saves_home_linea": 2.5,
        "saves_away_linea": 2.5,
        "sot_totales_linea": 8.5,
        "sot_totales_under_linea": 10.5,
        "sot_home_linea": 4.5,
        "sot_home_under_linea": 6.5,
        "sot_away_linea": 4.5,
        "sot_away_under_linea": 6.5,
        "shots_totales_linea": 22.5,
        "shots_totales_under_linea": 26.5,
        "shots_home_linea": 11.5,
        "shots_home_under_linea": 14.5,
        "shots_away_linea": 12.5,
        "shots_away_under_linea": 15.5,
        "fouls_totales_linea": 21.5,
        "fouls_totales_under_linea": 25.5,
        "fouls_home_linea": 10.5,
        "fouls_home_under_linea": 13.5,
        "fouls_away_linea": 11.5,
        "fouls_away_under_linea": 14.5,
        "btts_yes": np.mean((gh > 0) & (ga > 0)) * 100,
        "btts_no": np.mean((gh == 0) | (ga == 0)) * 100,
        "goles_over": np.mean((gh + ga) > 2.5) * 100,
        "goles_under": np.mean((gh + ga) <= 2.5) * 100,
        "goles_1t_over": np.mean((gh_1t + ga_1t) > 0.5) * 100,
        "goles_1t_under": np.mean((gh_1t + ga_1t) <= 0.5) * 100,
        "corners_totales_over": np.mean((ch + ca) > 8.5) * 100,
        "corners_totales_under": np.mean((ch + ca) < 11.5) * 100,
        "corners_home_over": np.mean(ch > 3.5) * 100,
        "corners_home_under": np.mean(ch < 5.5) * 100,
        "corners_away_over": np.mean(ca > 5.5) * 100,
        "corners_away_under": np.mean(ca < 8.5) * 100,
        "cards_totales_over": np.mean((card_h + card_a) > 3.5) * 100,
        "cards_totales_under": np.mean((card_h + card_a) < 5.5) * 100,
        "cards_home_over": np.mean(card_h > 1.5) * 100,
        "cards_home_under": np.mean(card_h < 2.5) * 100,
        "cards_away_over": np.mean(card_a > 1.5) * 100,
        "cards_away_under": np.mean(card_a < 2.5) * 100,
        "offsides_totales_over": np.mean((off_h + off_a) > 3.5) * 100,
        "offsides_totales_under": np.mean((off_h + off_a) < 5.5) * 100,
        "offsides_home_over": np.mean(off_h > 1.5) * 100,
        "offsides_home_under": np.mean(off_h < 2.5) * 100,
        "offsides_away_over": np.mean(off_a > 1.5) * 100,
        "offsides_away_under": np.mean(off_a < 2.5) * 100,
        "saves_totales_over": np.mean((sav_h + sav_a) > 5.5) * 100,
        "saves_totales_under": np.mean((sav_h + sav_a) < 7.5) * 100,
        "saves_home_over": np.mean(sav_h > 2.5) * 100,
        "saves_away_over": np.mean(sav_a > 2.5) * 100,
        "sot_totales_over": np.mean((sot_h + sot_a) > 8.5) * 100,
        "sot_totales_under": np.mean((sot_h + sot_a) < 10.5) * 100,
        "sot_home_over": np.mean(sot_h > 4.5) * 100,
        "sot_home_under": np.mean(sot_h < 6.5) * 100,
        "sot_away_over": np.mean(sot_a > 4.5) * 100,
        "sot_away_under": np.mean(sot_a < 6.5) * 100,
        "shots_totales_over": np.mean((sh_h + sh_a) > 22.5) * 100,
        "shots_totales_under": np.mean((sh_h + sh_a) < 26.5) * 100,
        "shots_home_over": np.mean(sh_h > 11.5) * 100,
        "shots_home_under": np.mean(sh_h < 14.5) * 100,
        "shots_away_over": np.mean(sh_a > 12.5) * 100,
        "shots_away_under": np.mean(sh_a < 15.5) * 100,
        "fouls_totales_over": np.mean((foul_h + foul_a) > 21.5) * 100,
        "fouls_totales_under": np.mean((foul_h + foul_a) < 25.5) * 100,
        "fouls_home_over": np.mean(foul_h > 10.5) * 100,
        "fouls_home_under": np.mean(foul_h < 13.5) * 100,
        "fouls_away_over": np.mean(foul_a > 11.5) * 100,
        "fouls_away_under": np.mean(foul_a < 14.5) * 100,
        "penalty_yes": np.mean(penalties == 1) * 100,
        "penalty_no": np.mean(penalties == 0) * 100,
        "score_both_halves_home": np.mean((gh_1t > 0) & (gh_2t > 0)) * 100,
        "score_both_halves_away": np.mean((ga_1t > 0) & (ga_2t > 0)) * 100,
        "ml_home": np.mean(gh > ga) * 100,
        "ml_draw": np.mean(gh == ga) * 100,
        "ml_away": np.mean(ga > gh) * 100,
        "dc_1x": np.mean(gh >= ga) * 100,
        "dc_x2": np.mean(ga >= gh) * 100,
        "dc_12": np.mean(gh != ga) * 100,
        "first_goal_home": np.mean((gh > 0) & (gh_1t >= ga_1t)) * 100,
        "first_goal_away": np.mean((ga > 0) & (ga_1t > gh_1t)) * 100,
        "first_goal_none": np.mean((gh == 0) & (ga == 0)) * 100,
        "win_half_home": np.mean((gh_1t > ga_1t) | (gh_2t > ga_2t)) * 100,
        "win_half_away": np.mean((ga_1t > gh_1t) | (ga_2t > gh_2t)) * 100,
    }
    return sim


def generar_reporte_partido(match, sim):
    mercados_evaluados = [
        ("Ambos anotan", sim["btts_yes"]),
        ("Ambos no anotan", sim["btts_no"]),
        (f"Over {sim['goles_linea']} goles partido", sim["goles_over"]),
        (f"Under {sim['goles_linea']} goles partido", sim["goles_under"]),
        (
            f"Over {sim['goles_1t_linea']} goles 1er tiempo",
            sim["goles_1t_over"],
        ),
        (
            f"Under {sim['goles_1t_linea']} goles 1er tiempo",
            sim["goles_1t_under"],
        ),
        (
            f"Over {sim['corners_totales_over_linea']} corners entre ambos",
            sim["corners_totales_over"],
        ),
        (
            f"Under {sim['corners_totales_under_linea']} corners entre ambos",
            sim["corners_totales_under"],
        ),
        (
            f"Over {sim['corners_home_over_linea']} corners {match['home']}",
            sim["corners_home_over"],
        ),
        (
            f"Under {sim['corners_home_under_linea']} corners {match['home']}",
            sim["corners_home_under"],
        ),
        (
            f"Over {sim['corners_away_over_linea']} corners {match['away']}",
            sim["corners_away_over"],
        ),
        (
            f"Under {sim['corners_away_under_linea']} corners {match['away']}",
            sim["corners_away_under"],
        ),
        (
            f"Over {sim['cards_totales_over_linea']} tarjetas entre ambos",
            sim["cards_totales_over"],
        ),
        (
            f"Under {sim['cards_totales_under_linea']} tarjetas entre ambos",
            sim["cards_totales_under"],
        ),
        (
            f"Over {sim['cards_home_over_linea']} tarjetas {match['home']}",
            sim["cards_home_over"],
        ),
        (
            f"Under {sim['cards_home_under_linea']} tarjetas {match['home']}",
            sim["cards_home_under"],
        ),
        (
            f"Over {sim['cards_away_over_linea']} tarjetas {match['away']}",
            sim["cards_away_over"],
        ),
        (
            f"Under {sim['cards_away_under_linea']} tarjetas {match['away']}",
            sim["cards_away_under"],
        ),
        (
            f"Over {sim['offsides_totales_linea']} fueras de lugar entre ambos",
            sim["offsides_totales_over"],
        ),
        (
            f"Under {sim['offsides_totales_under_linea']} fueras de lugar entre ambos",
            sim["offsides_totales_under"],
        ),
        (
            f"Over {sim['offsides_home_linea']} fueras de lugar {match['home']}",
            sim["offsides_home_over"],
        ),
        (
            f"Under {sim['offsides_home_under_linea']} fueras de lugar {match['home']}",
            sim["offsides_home_under"],
        ),
        (
            f"Over {sim['offsides_away_linea']} fueras de lugar {match['away']}",
            sim["offsides_away_over"],
        ),
        (
            f"Under {sim['offsides_away_under_linea']} fueras de lugar {match['away']}",
            sim["offsides_away_under"],
        ),
        (
            f"Over {sim['saves_totales_linea']} atajadas entre ambos porteros",
            sim["saves_totales_over"],
        ),
        (
            f"Under {sim['saves_totales_under_linea']} atajadas entre ambos porteros",
            sim["saves_totales_under"],
        ),
        (
            f"Over {sim['saves_home_linea']} atajadas portero {match['home']}",
            sim["saves_home_over"],
        ),
        (
            f"Over {sim['saves_away_linea']} atajadas portero {match['away']}",
            sim["saves_away_over"],
        ),
        (
            f"Over {sim['sot_totales_linea']} remates a portería entre ambos",
            sim["sot_totales_over"],
        ),
        (
            f"Under {sim['sot_totales_under_linea']} remates a portería entre ambos",
            sim["sot_totales_under"],
        ),
        (
            f"Over {sim['sot_home_linea']} remates a portería {match['home']}",
            sim["sot_home_over"],
        ),
        (
            f"Under {sim['sot_home_under_linea']} remates a portería {match['home']}",
            sim["sot_home_under"],
        ),
        (
            f"Over {sim['sot_away_linea']} remates a portería {match['away']}",
            sim["sot_away_over"],
        ),
        (
            f"Under {sim['sot_away_under_linea']} remates a portería {match['away']}",
            sim["sot_away_under"],
        ),
        (
            f"Over {sim['shots_totales_linea']} remates totales entre ambos",
            sim["shots_totales_over"],
        ),
        (
            f"Under {sim['shots_totales_under_linea']} remates totales entre ambos",
            sim["shots_totales_under"],
        ),
        (
            f"Over {sim['shots_home_linea']} remates totales {match['home']}",
            sim["shots_home_over"],
        ),
        (
            f"Under {sim['shots_home_under_linea']} remates totales {match['home']}",
            sim["shots_home_under"],
        ),
        (
            f"Over {sim['shots_away_linea']} remates totales {match['away']}",
            sim["shots_away_over"],
        ),
        (
            f"Under {sim['shots_away_under_linea']} remates totales {match['away']}",
            sim["shots_away_under"],
        ),
        (
            f"Over {sim['fouls_totales_linea']} faltas entre ambos",
            sim["fouls_totales_over"],
        ),
        (
            f"Under {sim['fouls_totales_under_linea']} faltas entre ambos",
            sim["fouls_totales_under"],
        ),
        (
            f"Over {sim['fouls_home_linea']} faltas {match['home']}",
            sim["fouls_home_over"],
        ),
        (
            f"Under {sim['fouls_home_under_linea']} faltas {match['home']}",
            sim["fouls_home_under"],
        ),
        (
            f"Over {sim['fouls_away_linea']} faltas {match['away']}",
            sim["fouls_away_over"],
        ),
        (
            f"Under {sim['fouls_away_under_linea']} faltas {match['away']}",
            sim["fouls_away_under"],
        ),
        ("Penalti en el encuentro - Sí", sim["penalty_yes"]),
        ("Penalti en el encuentro - No", sim["penalty_no"]),
        (f"{match['home']} marca en ambos tiempos", sim["score_both_halves_home"]),
        (f"{match['away']} marca en ambos tiempos", sim["score_both_halves_away"]),
        (f"Gana {match['home']}", sim["ml_home"]),
        ("Empate", sim["ml_draw"]),
        (f"Gana {match['away']}", sim["ml_away"]),
        (f"Doble Oportunidad 1X ({match['home']} o Empate)", sim["dc_1x"]),
        (f"Doble Oportunidad X2 ({match['away']} o Empate)", sim["dc_x2"]),
        ("Doble Oportunidad 12 (Sin Empate)", sim["dc_12"]),
        (f"Primer gol {match['home']}", sim["first_goal_home"]),
        (f"Primer gol {match['away']}", sim["first_goal_away"]),
        (f"{match['home']} gana alguna mitad", sim["win_half_home"]),
        (f"{match['away']} gana alguna mitad", sim["win_half_away"]),
    ]

    candidatos_85 = [
        (nombre, prob) for nombre, prob in mercados_evaluados if prob >= 85.0
    ]

    if candidatos_85:
        candidatos_85.sort(key=lambda x: x[1], reverse=True)
        top_pick, top_prob = candidatos_85[0]
        apuesta_derecha_txt = f"{top_pick} ({top_prob:.0f}%)"
    else:
        apuesta_derecha_txt = "Sin selecciones directas mayores o iguales al 85% para este partido"

    reporte_texto = f"""
{match['home']} vs {match['away']}

Ambos anotan ({sim['btts_yes']:.0f}%) | Ambos no anotan ({sim['btts_no']:.0f}%)

Goles partido: Over {sim['goles_linea']} ({sim['goles_over']:.0f}%) | Under {sim['goles_linea']} ({sim['goles_under']:.0f}%)
Goles 1er tiempo: Over {sim['goles_1t_linea']} ({sim['goles_1t_over']:.0f}%) | Under {sim['goles_1t_linea']} ({sim['goles_1t_under']:.0f}%)

Corners entre ambos: over {sim['corners_totales_over_linea']}({sim['corners_totales_over']:.0f}%) under {sim['corners_totales_under_linea']}({sim['corners_totales_under']:.0f}%)
Over corners {match['home']}: {sim['corners_home_over_linea']} corners ({sim['corners_home_over']:.0f}%)
Under corners {match['home']}: {sim['corners_home_under_linea']} ({sim['corners_home_under']:.0f}%)
Over corners {match['away']}: {sim['corners_away_over_linea']} corners ({sim['corners_away_over']:.0f}%)
Under corners {match['away']}: {sim['corners_away_under_linea']} ({sim['corners_away_under']:.0f}%)

Tarjetas entre ambos: over {sim['cards_totales_over_linea']}({sim['cards_totales_over']:.0f}%) under {sim['cards_totales_under_linea']}({sim['cards_totales_under']:.0f}%)
Over tarjetas {match['home']}: {sim['cards_home_over_linea']} ({sim['cards_home_over']:.0f}%)
Under tarjetas {match['home']}: {sim['cards_home_under_linea']} ({sim['cards_home_under']:.0f}%)
Over tarjetas {match['away']}: {sim['cards_away_over_linea']} ({sim['cards_away_over']:.0f}%)
Under tarjetas {match['away']}: {sim['cards_away_under_linea']} ({sim['cards_away_under']:.0f}%)

Fueras de lugar entre ambos: over {sim['offsides_totales_linea']} ({sim['offsides_totales_over']:.0f}%) | under {sim['offsides_totales_under_linea']} ({sim['offsides_totales_under']:.0f}%)
Fueras de lugar {match['home']}: over {sim['offsides_home_linea']} ({sim['offsides_home_over']:.0f}%) | under {sim['offsides_home_under_linea']} ({sim['offsides_home_under']:.0f}%)
Fueras de lugar {match['away']}: over {sim['offsides_away_linea']} ({sim['offsides_away_over']:.0f}%) | under {sim['offsides_away_under_linea']} ({sim['offsides_away_under']:.0f}%)

Atajadas porteros entre ambos: over {sim['saves_totales_linea']} ({sim['saves_totales_over']:.0f}%) | under {sim['saves_totales_under_linea']} ({sim['saves_totales_under']:.0f}%)
Atajadas portero {match['home']}: over {sim['saves_home_linea']} ({sim['saves_home_over']:.0f}%)
Atajadas portero {match['away']}: over {sim['saves_away_linea']} ({sim['saves_away_over']:.0f}%)

Remates a portería entre ambos: over {sim['sot_totales_linea']} ({sim['sot_totales_over']:.0f}%) | under {sim['sot_totales_under_linea']} ({sim['sot_totales_under']:.0f}%)
Remates a portería {match['home']}: over {sim['sot_home_linea']} ({sim['sot_home_over']:.0f}%) | under {sim['sot_home_under_linea']} ({sim['sot_home_under']:.0f}%)
Remates a portería {match['away']}: over {sim['sot_away_linea']} ({sim['sot_away_over']:.0f}%) | under {sim['sot_away_under_linea']} ({sim['sot_away_under']:.0f}%)

Remates totales entre ambos: over {sim['shots_totales_linea']} ({sim['shots_totales_over']:.0f}%) | under {sim['shots_totales_under_linea']} ({sim['shots_totales_under']:.0f}%)
Remates totales {match['home']}: over {sim['shots_home_linea']} ({sim['shots_home_over']:.0f}%) | under {sim['shots_home_under_linea']} ({sim['shots_home_under']:.0f}%)
Remates totales {match['away']}: over {sim['shots_away_linea']} ({sim['shots_away_over']:.0f}%) | under {sim['shots_away_under_linea']} ({sim['shots_away_under']:.0f}%)

Faltas entre ambos: over {sim['fouls_totales_linea']} ({sim['fouls_totales_over']:.0f}%) | under {sim['fouls_totales_under_linea']} ({sim['fouls_totales_under']:.0f}%)
Faltas {match['home']}: over {sim['fouls_home_linea']} ({sim['fouls_home_over']:.0f}%) | under {sim['fouls_home_under_linea']} ({sim['fouls_home_under']:.0f}%)
Faltas {match['away']}: over {sim['fouls_away_linea']} ({sim['fouls_away_over']:.0f}%) | under {sim['fouls_away_under_linea']} ({sim['fouls_away_under']:.0f}%)

Penalti en el encuentro: Sí ({sim['penalty_yes']:.0f}%) | No ({sim['penalty_no']:.0f}%)
Marca en ambos tiempos: {match['home']} Sí ({sim['score_both_halves_home']:.0f}%) | {match['away']} Sí ({sim['score_both_halves_away']:.0f}%)

Moneyline: {match['home']} ({sim['ml_home']:.0f}%) | Empate ({sim['ml_draw']:.0f}%) | {match['away']} ({sim['ml_away']:.0f}%)
Doble oportunidad: 1X ({sim['dc_1x']:.0f}%) | X2 ({sim['dc_x2']:.0f}%) | 12 ({sim['dc_12']:.0f}%)

Primer gol: {match['home']} ({sim['first_goal_home']:.0f}%) | {match['away']} ({sim['first_goal_away']:.0f}%) | Ninguno ({sim['first_goal_none']:.0f}%)
Ganador de mitad: {match['home']} gana alguna mitad ({sim['win_half_home']:.0f}%) | {match['away']} gana alguna mitad ({sim['win_half_away']:.0f}%)

Apuesta derecha con 85% de probabilidad: {apuesta_derecha_txt}
"""
    return reporte_texto


def analyze_all_matches(target_matches=None):
    if target_matches is None:
        target_matches = [
            {
                "home": "Equipo Local",
                "away": "Equipo Visitante",
                "exp_g_home": 1.6,
                "exp_g_away": 1.2,
                "exp_c_home": 5.2,
                "exp_c_away": 4.1,
                "exp_card_home": 2.1,
                "exp_card_away": 2.4,
                "exp_off_home": 2.0,
                "exp_off_away": 1.8,
                "exp_sav_home": 3.2,
                "exp_sav_away": 3.8,
                "exp_sot_home": 5.1,
                "exp_sot_away": 4.3,
                "exp_sh_home": 13.5,
                "exp_sh_away": 11.2,
                "exp_foul_home": 11.8,
                "exp_foul_away": 12.5,
            }
        ]

    reportes = []
    for match in target_matches:
        simulacion = run_monte_carlo_analysis(match)
        texto_partido = generar_reporte_partido(match, simulacion)
        reportes.append(texto_partido)

    salida_final = "\n" + "=" * 40 + "\n".join(reportes)
    print(salida_final)
    return salida_final


if __name__== "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=analyze_all_matches, trigger="cron", hour=21, minute=0
    )
    scheduler.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
