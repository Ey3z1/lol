from flask import Flask, render_template, jsonify, request
import mysql.connector
from datetime import datetime, timedelta
import time
import requests
from game_importer import importar_diferencial, obtener_torneos_de_bbdd, obtener_torneos_con_matches_de_bbdd  # Importación clave
from game_select import obtener_games_por_match,obtener_matches_por_torneo, obtener_partidas_kills_equipo,obtener_torneo_por_id, obtener_campeon_por_id,obtener_equipos_con_imagen,obtener_champions_con_imagen, obtener_jugadores_por_equipos, obtener_jugador_por_id, obtener_partidas_jugador  # Importación clave
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
    team1 = data.get('team1')
    team2 = data.get('team2')
    team1_dict = ast.literal_eval(team1)
    team2_dict = ast.literal_eval(team2)
    team1_id = team1_dict['id']
    cuota1 = float(data.get('cuota1'))
    cuota2 = float(data.get('cuota2'))
    bans = data.getlist('bans[]')

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
    team1_id = team1_dict['id']
    team1_name = team1_dict['name']
    team1_img = team1_dict['image']   # <--- URL de la imagen
    team2_id = team2_dict['id']
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

@app.route('/procesar_kills', methods=['POST'])
def procesar_kills():
    """
    Procesa el cálculo de Expected Value para líneas de kills de equipos
    """
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
    
    
    # Calcular probabilidades implícitas de victoria
    prob_team1_win = (1 / cuota1) / ((1 / cuota1) + (1 / cuota2))
    prob_team2_win = 1 - prob_team1_win
    
    # Obtener partidas históricas de ambos equipos
    partidas_team1 = obtener_partidas_kills_equipo(team1_id)
    
    partidas_team2 = obtener_partidas_kills_equipo(team2_id)
    
    equipos_stats = []
    
    # Procesar Team 1
    if partidas_team1:
        team1_name = partidas_team1[0]['equipo_nombre']
        team1_img = partidas_team1[0]['equipo_img']
        # Separar partidas en victorias y derrotas
        victorias_t1 = [p for p in partidas_team1 if p['ganado_kills']]
        derrotas_t1 = [p for p in partidas_team1 if not p['ganado_kills']]
        
        # Calcular estadísticas para superar la línea
        supero_victorias_t1 = sum(1 for p in victorias_t1 if p['diferencia_kills'] >= linea_kills_team1)
        supero_derrotas_t1 = sum(1 for p in derrotas_t1 if p['diferencia_kills'] >= linea_kills_team1)
        
        # Probabilidades condicionales
        prob_over_win_t1 = supero_victorias_t1 / len(victorias_t1) if len(victorias_t1) > 0 else 0
        prob_over_lose_t1 = supero_derrotas_t1 / len(derrotas_t1) if len(derrotas_t1) > 0 else 0
        
        # Probabilidad total de superar la línea
        prob_over_total_t1 = (prob_over_win_t1 * prob_team1_win) + (prob_over_lose_t1 * prob_team2_win)
        prob_under_total_t1 = 1 - prob_over_total_t1
        
        # Calcular porcentajes para mostrar
        prob_superar_victorias_t1 = (supero_victorias_t1 / len(victorias_t1) * 100) if len(victorias_t1) > 0 else 0
        prob_superar_derrotas_t1 = (supero_derrotas_t1 / len(derrotas_t1) * 100) if len(derrotas_t1) > 0 else 0
        prob_superar_total_t1 = ((supero_victorias_t1 + supero_derrotas_t1) / len(partidas_team1) * 100) if len(partidas_team1) > 0 else 0
        
        equipos_stats.append({
            'team_id': team1_id,
            'team_name': team1_name,
            'team_img': team1_img,
            'linea': linea_kills_team1,
            'prob_over': round(prob_over_total_t1 * 100, 2),
            'prob_under': round(prob_under_total_t1 * 100, 2),
            'supero_victorias': supero_victorias_t1,
            'supero_derrotas': supero_derrotas_t1,
            'total_victorias': len(victorias_t1),
            'total_derrotas': len(derrotas_t1),
            'total_partidas': len(partidas_team1),
            'prob_superar_victorias': round(prob_superar_victorias_t1, 2),
            'prob_superar_derrotas': round(prob_superar_derrotas_t1, 2),
            'prob_superar_total': round(prob_superar_total_t1, 2),
            'partidas': partidas_team1
        })
    
    # Procesar Team 2 
    if partidas_team2:
        team2_name = partidas_team2[0]['equipo_nombre']
        team2_img = partidas_team2[0]['equipo_img']
        # Separar partidas en victorias y derrotas
        victorias_t2 = [p for p in partidas_team2 if p['ganado_kills']]
        derrotas_t2 = [p for p in partidas_team2 if not p['ganado_kills']]
        
        # Calcular estadísticas para superar la línea
        supero_victorias_t2 = sum(1 for p in victorias_t2 if p['diferencia_kills'] <= linea_kills_team2)
        supero_derrotas_t2 = sum(1 for p in derrotas_t2 if p['diferencia_kills'] <= linea_kills_team2)
        
        # Probabilidades condicionales
        prob_over_win_t2 = supero_victorias_t2 / len(victorias_t2) if len(victorias_t2) > 0 else 0
        prob_over_lose_t2 = supero_derrotas_t2 / len(derrotas_t2) if len(derrotas_t2) > 0 else 0
        
        # Probabilidad total de superar la línea
        prob_over_total_t2 = (prob_over_win_t2 * prob_team2_win) + (prob_over_lose_t2 * prob_team1_win)
        prob_under_total_t2 = 1 - prob_over_total_t2
        
        # Calcular porcentajes para mostrar
        prob_superar_victorias_t2 = (supero_victorias_t2 / len(victorias_t2) * 100) if len(victorias_t2) > 0 else 0
        prob_superar_derrotas_t2 = (supero_derrotas_t2 / len(derrotas_t2) * 100) if len(derrotas_t2) > 0 else 0
        prob_superar_total_t2 = ((supero_victorias_t2 + supero_derrotas_t2) / len(partidas_team2) * 100) if len(partidas_team2) > 0 else 0
        
        equipos_stats.append({
            'team_id': team2_id,
            'team_name': team2_name,
            'team_img': team2_img,
            'linea': abs(linea_kills_team2),  # Usar valor absoluto para la línea
            'prob_over': round(prob_over_total_t2 * 100, 2),
            'prob_under': round(prob_under_total_t2 * 100, 2),
            'supero_victorias': supero_victorias_t2,
            'supero_derrotas': supero_derrotas_t2,
            'total_victorias': len(victorias_t2),
            'total_derrotas': len(derrotas_t2),
            'total_partidas': len(partidas_team2),
            'prob_superar_victorias': round(prob_superar_victorias_t2, 2),
            'prob_superar_derrotas': round(prob_superar_derrotas_t2, 2),
            'prob_superar_total': round(prob_superar_total_t2, 2),
            'partidas': partidas_team2
        })
    
    return render_template(
        'kills_calculo.html',  # Nuevo template para mostrar resultados de kills
        equipos_stats=equipos_stats,
        team1_name=team1_name,
        team2_name=team2_name,
        team1_img=team1_img,
        team2_img=team2_img,
        team1_id=team1_id,
        team2_id=team2_id,
        prob_team1=round(prob_team1_win * 100, 2),
        prob_team2=round(prob_team2_win * 100, 2),
        linea_team1=linea_kills_team1,
        linea_team2=abs(linea_kills_team2)
    )



def calcular_probabilidad_superar_linea(avg_kills, linea):
    # Implementación simplificada (usar distribución normal en producción)
    return 1 / (1 + math.exp(-(avg_kills - linea)))

if __name__ == '__main__':
    app.run(debug=True)