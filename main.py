import json
from flask import Flask, render_template, jsonify, request
import mysql.connector
from datetime import datetime, timedelta
import time
import requests
from game_importer import importar_diferencial, obtener_torneos_de_bbdd, obtener_torneos_con_matches_de_bbdd  # Importación clave
from game_insert import cambiar_tier, insert_busquedas_ev
from game_select import get_searches_by_id, get_ultimas_busquedas, obtener_clasificacion_torneo, obtener_games_por_match,obtener_matches_por_torneo, obtener_partidas_kills_equipo, obtener_stats_equipos, obtener_stats_torneo,obtener_torneo_por_id, obtener_campeon_por_id,obtener_equipos_con_imagen,obtener_champions_con_imagen, obtener_jugadores_por_equipos, obtener_jugador_por_id, obtener_partidas_jugador, obtener_torneos_activos  # Importación clave
import math
from datetime import datetime
import ast
from config_local import DB_CONFIG, API_KEY


app = Flask(__name__)

HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://lolesports.com"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/descargar_games', methods=['POST'])
def descargar_games():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        importar_diferencial(connection)  # Función de tu script
        return jsonify({"status": "success", "message": "✅ Games descargados correctamente"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"❌ Error: {str(e)}"})
    finally:
        if connection and connection.is_connected():
            connection.close()

@app.route('/seleccionar-torneos', methods=['GET', 'POST'])
def seleccionar_torneos():
    if request.method == 'POST':
        # Obtener los IDs de torneos seleccionados
        torneos_seleccionados = request.form.getlist('tournamentes')
        modo = request.form.get('modo_importacion')

        importar_con_leaguepedia = modo == 'leaguepedia'
        
        # Aquí integras tu código de descarga
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            importar_diferencial(connection, torneos_seleccionados, importar_con_leaguepedia=importar_con_leaguepedia)
            mensaje = "✅ Descarga completada para torneos seleccionados"
        except Exception as e:
            mensaje = f"❌ Error: {str(e)}"
            print(mensaje)
            
        return render_template('seleccion_torneos.html', 
                            torneos=obtener_torneos_de_bbdd(),
                            mensaje=mensaje)
    
    return render_template('seleccion_torneos.html', 
                         torneos=obtener_torneos_de_bbdd())

@app.route('/descargar-torneos-activos', methods=['POST'])
def descargar_torneos_activos():
    try:
        torneos_activos = obtener_torneos_activos()

        if not torneos_activos:
            mensaje = "⚠️ No hay torneos activos para descargar."
        else:
            # Conexión para importar_diferencial (según tu lógica puede ser necesaria)
            connection = mysql.connector.connect(**DB_CONFIG)
            importar_diferencial(connection, torneos_activos, True)
            connection.close()
            mensaje = "✅ Descarga completada para torneos activos."
    except Exception as e:
        mensaje = f"❌ Error: {str(e)}"
        print(mensaje)

    torneos = obtener_torneos_con_matches_de_bbdd()
    return render_template('torneos.html', torneos=torneos, mensaje=mensaje)



@app.route('/torneo')
def ver_torneos():
    torneos = obtener_torneos_con_matches_de_bbdd()
    return render_template('torneos.html', torneos=torneos)

@app.route('/torneo/<int:torneo_id>')
def ver_torneo(torneo_id):
    # Obtener información del torneo (opcional)
    torneo = obtener_torneo_por_id(torneo_id)
    
    # Obtener matches y games asociados al torneo
    matches = obtener_matches_por_torneo(torneo_id)

    return render_template(
        'lista_matches.html',
        torneo=torneo,
        matches=matches
    )

@app.route('/torneo/<int:torneo_id>/equipo/<int:team_id>/tier', methods=['POST'])
def actualizar_tier(torneo_id, team_id):
    data = request.get_json()
    new_tier = data.get('tier')
    # Validar que new_tier sea un entero válido
    try:
        new_tier = int(new_tier)
        assert 1 <= new_tier <= 5
    except:
        return jsonify({"error":"Tier inválido"}), 400
    cambiar_tier(torneo_id, new_tier,team_id)
   
    return jsonify({"success":True}), 200

@app.route('/torneo/<int:torneo_id>/clasificacion')
def clasificacion_torneo(torneo_id):
    # Obtener información del torneo (opcional)
    torneo = obtener_torneo_por_id(torneo_id)
    
    # Obtener matches y games asociados al torneo
    clasificacion = obtener_clasificacion_torneo(torneo_id)

    return render_template(
        'clasificacion_torneo.html',
        torneo=torneo,
        clasificacion=clasificacion
    )

@app.route('/torneo/<int:torneo_id>/stats')
def stats_torneo(torneo_id):
    # Obtener información del torneo (opcional)
    torneo = obtener_torneo_por_id(torneo_id)
    
    # Obtener matches y games asociados al torneo
    stats = obtener_stats_torneo(torneo_id)
    stats_equipos = obtener_stats_equipos(torneo_id)
    return render_template(
        'stats_torneo.html',
        torneo=torneo,
        stats=stats,
        stats_equipos =stats_equipos
    )

# @app.route('/match/<int:match_id>')
# def ver_match(match_id):
#     # Obtener games del match
#     games = obtener_games_por_match(match_id)
    
#     # Obtener info del match (opcional)
#     match = obtener_match_por_id(match_id)
    
#     return render_template(
#         'ver_match.html',
#         match=match,
#         games=games
#     )

@app.route('/games_por_match/<int:match_id>')
def games_por_match(match_id):
    games = obtener_games_por_match(match_id)
    return jsonify(games)

def calcular_linea(avg_kills, probabilidad):
    """Calcula la línea ajustada basada en la probabilidad del equipo"""
    max_ajuste = 0.5  # Máximo ajuste de ±1.0 kills
    ajuste = (0.5 - (1-probabilidad)) * 2 * max_ajuste
    linea = avg_kills + ajuste
    entero = round(linea)
    linea_final = entero - 0.5  # Forzar formato X.5
    return max(linea_final, 0.5)  # Mínimo 0.5

@app.route('/futuras_partidas', methods=['GET', 'POST'])
def futuras_partidas():
    equipos = obtener_equipos_con_imagen()
    champions = obtener_champions_con_imagen()

    if request.method == 'POST':
        team1_id = request.form.get('team1')
        team2_id = request.form.get('team2')
        
        try:
            cuota1 = float(request.form.get('cuota1')) if request.form.get('cuota1') else None
            cuota2 = float(request.form.get('cuota2')) if request.form.get('cuota2') else None
        except ValueError:
            cuota1 = cuota2 = None

        # Calcular probabilidades usando fórmula p1/(p1+p2)
        prob_team1, prob_team2 = calcular_probabilidades(cuota1, cuota2)
        
        # Obtener jugadores de ambos equipos
        jugadores = obtener_jugadores_por_equipos(team1_id, team2_id)
        
        # Separar jugadores por equipo y calcular líneas
        jugadores_team1 = []
        jugadores_team2 = []
        
        for jugador in jugadores:
            if jugador['team_id'] == int(team1_id):
                linea = calcular_linea(jugador['avg_kills'], prob_team1)
                jugadores_team1.append({**jugador, 'linea': linea})
            else:
                linea = calcular_linea(jugador['avg_kills'], prob_team2)
                jugadores_team2.append({**jugador, 'linea': linea})

        return render_template('futuras_partidas.html',
                            equipos=equipos,
                            team1=next((e for e in equipos if e['id'] == int(team1_id)), None),
                            team2=next((e for e in equipos if e['id'] == int(team2_id)), None),
                            jugadores_team1=jugadores_team1,
                            jugadores_team2=jugadores_team2,
                            cuota1=cuota1,
                            cuota2=cuota2,
                            champions = champions,
                            prob_team1=round(prob_team1*100, 1),
                            prob_team2=round(prob_team2*100, 1))
    
    return render_template('futuras_partidas.html', equipos=equipos)

def calcular_probabilidades(cuota1, cuota2):
    try:
        p1 = 1/cuota1 if cuota1 and cuota1 > 0 else 0
        p2 = 1/cuota2 if cuota2 and cuota2 > 0 else 0
        total = p1 + p2
        return (p1/total, p2/total) if total > 0 else (0.5, 0.5)
    except:
        return (0.5, 0.5)
    
@app.route('/ev_calculo', methods=['POST'])
def ev_calculo():
    data = request.form
    data_dict = data.to_dict()

    bans = data.getlist('bans[]')
    data_dict['bans[]'] = bans
    connection = mysql.connector.connect(**DB_CONFIG)
    team1 = data.get('team1')
    team2 = data.get('team2')
    team1_dict = ast.literal_eval(team1)
    team2_dict = ast.literal_eval(team2)
    team1_id = team1_dict['id']
    team2_id = team2_dict['id']
    insert_busquedas_ev(connection, data_dict, team1_id, team2_id)
    cuota1 = float(data.get('cuota1'))
    cuota2 = float(data.get('cuota2'))

    banned_champs = []
    for ban_id in bans:
        if ban_id:  # Verificar que no esté vacío
            ban_id_int = int(ban_id)
            campeon = obtener_campeon_por_id(ban_id_int)
            if campeon:
                banned_champs.append({
                    'id': ban_id,
                    'name': campeon['name'],
                    'img': campeon['img']
                })

    # Extraer datos de equipos
    team1_name = team1_dict['name']
    team1_img = team1_dict['image']   # <--- URL de la imagen
    team2_name = team2_dict['name']
    team2_img = team2_dict['image']   # <--- URL de la imagen
    
    # Calcular probabilidades implícitas de victoria y derrota
    prob_team1 = (1 / cuota1) / ((1 / cuota1) + (1 / cuota2))
    prob_team2 = 1 - prob_team1
    
    jugadores = []
    for key in data:
        if key.startswith('cuotaOver') and data.get(key):
            jugador_id = key.split('_')[1]
            linea =  float(data.get(f'linea_{jugador_id}'))
            cuota_over = float(data.get(f'cuotaOver_{jugador_id}'))
            cuota_under = float(data.get(f'cuotaUnder_{jugador_id}'))
            
            jugador = obtener_jugador_por_id(jugador_id)
            partidas = obtener_partidas_jugador(jugador_id, bans)
            
            # Determinar a qué equipo pertenece
            if jugador['team_id'] == int(team1_id):
                prob_win = prob_team1
                prob_lose = prob_team2
            else:
                prob_win = prob_team2
                prob_lose = prob_team1
                
            # Separar partidas en victorias y derrotas
            victorias = [p for p in partidas if p['resultado']]
            derrotas = [p for p in partidas if not p['resultado']]
            
            # Calcular porcentajes condicionales
            supero_victorias = sum(1 for p in victorias if p['kills'] >= linea)
            supero_derrotas = sum(1 for p in derrotas if p['kills'] >= linea)
            total_supero = supero_victorias + supero_derrotas
            
            # Probabilidades condicionales
            prob_over_win = supero_victorias / len(victorias) if len(victorias) > 0 else 0
            prob_over_lose = supero_derrotas / len(derrotas) if len(derrotas) > 0 else 0
            prob_over_total = (prob_over_win * prob_win) + (prob_over_lose * prob_lose)
            prob_under_total = 1 - prob_over_total
            # Calcular porcentajes
            prob_superar_victorias = (supero_victorias / len(victorias) * 100) if len(victorias) > 0 else 0
            prob_superar_derrotas = (supero_derrotas / len(derrotas) * 100) if len(derrotas) > 0 else 0
            total_partidas = len(partidas)
            prob_superar_total = (supero_victorias + supero_derrotas) / total_partidas * 100 if total_partidas > 0 else 0
            
            # Cálculo de EVs
            ev_over = (cuota_over - 1) * prob_over_total - (1 - prob_over_total)
            ev_under = (cuota_under - 1) * prob_under_total - (1 - prob_under_total)
            
            jugadores.append({
                'id': jugador_id,
                'nickname': jugador['nickname'],
                'linea': linea,
                'team_id': jugador['team_id'],
                'cuota_over': cuota_over,
                'cuota_under': cuota_under,
                'prob_over': round(prob_over_total * 100, 2),
                'prob_under': round(prob_under_total * 100, 2),
                'ev_over': round(ev_over, 2),
                'ev_under': round(ev_under, 2),
                'supero_victorias': supero_victorias,
                'supero_derrotas': supero_derrotas,
                'total_victorias': len(victorias),
                'total_derrotas': len(derrotas),
                'partidas': partidas,
                'prob_superar_victorias': round(prob_superar_victorias, 2),
                'prob_superar_derrotas': round(prob_superar_derrotas, 2),
                'prob_superar_total': round(prob_superar_total, 2)
            })
    
    return render_template(
        'ev_calculo.html',
        jugadores=jugadores,
        banned_champs=banned_champs,
        team1_name=team1_name,
        team2_name=team2_name,
        team1_img=team1_img,
        team2_img=team2_img,
        team1_id = team1_id,
        team2_id = team2_id,
        prob_team1=round(prob_team1*100, 2),
        prob_team2=round(prob_team2*100, 2)
    )

@app.route('/calculadora_ev', methods=['GET'])
def calculadora_ev():
    # Si no hay parámetros, muestro la página con el formulario.
    cuota = request.args.get('cuota')
    prob = request.args.get('prob')

    if cuota is None or prob is None:
        # Entrego la página HTML con el formulario para ingresar datos.
        return render_template('calculadora_ev.html')

    # Si llegaron parámetros, intento hacer el cálculo EV
    try:
        cuota = float(cuota)
        prob = float(prob)
    except ValueError:
        return jsonify({'error': 'Parámetros inválidos, usa número para cuota y probabilidad.'}), 400

    # cálculo EV = (H - 1)*I - (1 - I)
    ev = (cuota - 1) * prob - (1 - prob)
    return jsonify({'ev': ev})

@app.route('/get_previous_searches', methods=['GET'])
def get_previous_searches():
    searches = get_ultimas_busquedas()
    return jsonify(searches)

@app.route('/get_search_data/<int:search_id>', methods=['GET'])
def get_search_data(search_id):
    result = get_searches_by_id(search_id)
    
    if result:
        # Convertir el JSON string de vuelta a objeto
        data = json.loads(result['datos_formulario'])
        data['team1_id'] = result['team1_id']
        data['team2_id'] = result['team2_id']
        return jsonify(data)
    
    return jsonify({'error': 'No encontrado'}), 404

@app.route('/procesar_kills', methods=['POST'])
def procesar_kills():
    data = request.form
    
    # Obtener datos del formulario
    team1_id = request.form.get('team1')
    team2_id = request.form.get('team2')
    
    try:
        cuota1 = float(request.form.get('cuota1')) if request.form.get('cuota1') else None
        cuota2 = float(request.form.get('cuota2')) if request.form.get('cuota2') else None
    except ValueError:
        cuota1 = cuota2 = None
    
    linea_kills_team1 = float(data.get('linea_kills_team1'))
    linea_kills_team2 = float(data.get('linea_kills_team2'))
    
    # Determinar favorito y underdog por signo de línea
    favorito_id, underdog_id, linea_fav, linea_under = asignar_favorito_underdog_por_linea(
        linea_kills_team1, linea_kills_team2, team1_id, team2_id
    )
    


    prob_team1_win = (1 / cuota1) / ((1 / cuota1) + (1 / cuota2)) if cuota1 and cuota2 else 0.5
    prob_team2_win = 1 - prob_team1_win
    
    # Obtener partidas históricas
    partidas_favorito = obtener_partidas_kills_equipo(favorito_id)
    partidas_underdog = obtener_partidas_kills_equipo(underdog_id)
    
    equipos_stats = []
    # Calcular probabilidades implícitas de victoria
    if team1_id == favorito_id:
        prob_favorito = prob_team1_win
        prob_underdog = prob_team2_win
    else:
        prob_favorito = prob_team2_win
        prob_underdog = prob_team1_win
    
    # Procesar FAVORITO (línea negativa)
    if partidas_favorito:
        fav_name = partidas_favorito[0]['equipo_nombre']
        fav_img = partidas_favorito[0]['equipo_img']
        
        victorias_fav = [p for p in partidas_favorito if p['resultado']]
        derrotas_fav = [p for p in partidas_favorito if not p['resultado']]
        
        # Condición para favorito: diferencia_kills >= línea positiva
        supero_victorias_fav = sum(1 for p in victorias_fav if p['diferencia_kills'] + linea_fav > 0)
        supero_derrotas_fav = sum(1 for p in derrotas_fav if p['diferencia_kills'] + linea_fav >0)
        
        # Cálculos probabilísticos (igual que antes)
        prob_over_dado_victoria_fav = supero_victorias_fav / len(victorias_fav) if victorias_fav else 0
        prob_over_dado_derrota_fav = supero_derrotas_fav / len(derrotas_fav) if derrotas_fav else 0
        
        prob_over_total_fav = (prob_over_dado_victoria_fav * prob_favorito) + (prob_over_dado_derrota_fav * prob_underdog)
        prob_under_total_fav = 1 - prob_over_total_fav
        
        # Añadir estadísticas del favorito
        equipos_stats.append({
            'team_id': favorito_id,
            'team_name': fav_name,
            'team_img': fav_img,
            'linea': linea_fav,
            'tipo_apuesta': f'Gana por más de {linea_fav} kills',
            'prob_over': round(prob_over_total_fav * 100, 2),
            'prob_under': round(prob_under_total_fav * 100, 2),
            'supero_victorias': supero_victorias_fav,
            'supero_derrotas': supero_derrotas_fav,
            'total_victorias': len(victorias_fav),
            'total_derrotas': len(derrotas_fav),
            'total_partidas': len(partidas_favorito),
            'partidas': partidas_favorito
        })
    
    # Procesar UNDERDOG (línea negativa)
    if partidas_underdog:
        under_name = partidas_underdog[0]['equipo_nombre']
        under_img = partidas_underdog[0]['equipo_img']
        
        victorias_under = [p for p in partidas_underdog if p['resultado']]
        derrotas_under = [p for p in partidas_underdog if not p['resultado']]
        
        # Condición para underdog: diferencia_kills <= línea negativa
        supero_victorias_under = sum(1 for p in victorias_under if p['diferencia_kills'] + linea_under > 0)
        supero_derrotas_under = sum(1 for p in derrotas_under if p['diferencia_kills'] + linea_under > 0)
        # Cálculos probabilísticos (igual que antes)
        prob_over_dado_victoria_under = supero_victorias_under / len(victorias_under) if victorias_under else 0
        prob_over_dado_derrota_under = supero_derrotas_under / len(derrotas_under) if derrotas_under else 0
        
        prob_over_total_under = (prob_over_dado_victoria_under * prob_underdog) + (prob_over_dado_derrota_under * prob_favorito)
        prob_under_total_under = 1 - prob_over_total_under
        
        # Añadir estadísticas del underdog
        equipos_stats.append({
            'team_id': underdog_id,
            'team_name': under_name,
            'team_img': under_img,
            'linea': abs(linea_under),  # Mostrar valor absoluto
            'tipo_apuesta': f'Pierde por menos de {abs(linea_under)} kills',
            'prob_over': round(prob_over_total_under * 100, 2),
            'prob_under': round(prob_under_total_under * 100, 2),
            'supero_victorias': supero_victorias_under,
            'supero_derrotas': supero_derrotas_under,
            'total_victorias': len(victorias_under),
            'total_derrotas': len(derrotas_under),
            'total_partidas': len(partidas_underdog),
            'partidas': partidas_underdog
        })
    
    # MODELO COMBINADO
    modelo_combinado = None
    if len(equipos_stats) == 2:
        prob_fav_cubre = equipos_stats[0]['prob_over'] / 100
        prob_under_cubre = equipos_stats[1]['prob_over'] / 100
        
        # Probabilidad combinada ponderada
        prob_linea_se_cubre = (prob_fav_cubre * 0.6) + (prob_under_cubre * 0.4)
        
        modelo_combinado = {
            'prob_linea_se_cubre': round(prob_linea_se_cubre * 100, 2),
            'prob_linea_no_se_cubre': round((1 - prob_linea_se_cubre) * 100, 2),
            'recomendacion': 'OVER' if prob_linea_se_cubre > 0.52 else 'UNDER',
            'confianza': round(abs(prob_linea_se_cubre - 0.5) * 200, 2)
        }
    
    return render_template(
        'kills_calculo.html',
        equipos_stats=equipos_stats,
        team1_name=fav_name if 'fav_name' in locals() else 'Team 1',
        team2_name=under_name if 'under_name' in locals() else 'Team 2',
        team1_img=fav_img if 'fav_img' in locals() else '',
        team2_img=under_img if 'under_img' in locals() else '',
        prob_team1=round(prob_favorito * 100, 2),
        prob_team2=round(prob_underdog * 100, 2),
        modelo_combinado=modelo_combinado
    )


def asignar_favorito_underdog_por_linea(linea1, linea2, team1_id, team2_id):
    """
    Asigna favorito y underdog según el signo de la línea de kills
    
    Args:
        linea1 (float): Línea del equipo 1
        linea2 (float): Línea del equipo 2
        team1_id (str): ID equipo 1
        team2_id (str): ID equipo 2
        
    Returns:
        tuple: (favorito_id, underdog_id, linea_fav, linea_under)
    """
    if linea1 < 0 and linea2 > 0:
        return team1_id, team2_id, linea1, linea2
    elif linea1 > 0 and linea2 < 0:
        return team2_id, team1_id, linea2, linea1
    else:
        # Caso por defecto si los signos son iguales
        return team1_id, team2_id, abs(linea1), -abs(linea2)




def calcular_probabilidad_superar_linea(avg_kills, linea):
    # Implementación simplificada (usar distribución normal en producción)
    return 1 / (1 + math.exp(-(avg_kills - linea)))

if __name__ == '__main__':
    app.run(debug=True)