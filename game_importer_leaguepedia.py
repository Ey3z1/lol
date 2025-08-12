from datetime import datetime, timedelta
import leaguepedia_parser
from game_insert import  add_team_to_team_tournament, get_or_create_player, get_champion_id, insert_game_stats, insert_participant, insert_game, crear_match
from datetime import timedelta
from ratelimit import limits, sleep_and_retry
from game_select import obtener_max_index_leaguepedia
import traceback

def procesar_torneo_leaguepedia(connection, torneo_id, nombre_torneo):
    cursor = connection.cursor(dictionary=True)
    
    try:
        print(f"\n🏆 Procesando torneo {nombre_torneo}")
        
        # Paso 1: Obtener máximo índice existente
        max_index = obtener_max_index_leaguepedia(connection, nombre_torneo)
        print(f"🔝 Último índice procesado: {max_index}")
        # Paso 2: Obtener juegos desde Leaguepedia
        games = leaguepedia_parser.get_games(nombre_torneo)
        print(f"🎮 Juegos disponibles en API: {len(games)}")
        
        # Paso 3: Filtrar juegos nuevos
        nuevos_juegos = [(i, g) for i, g in enumerate(games) if i > max_index or max_index == 0]
        print(f"🆕 Juegos por procesar: {len(nuevos_juegos)}")
        
        # Paso 4: Procesar solo juegos nuevos
        for indice_original, game in nuevos_juegos:
            print(f"\n    🕹️ Procesando juego {indice_original+1}/{len(games)}")
            game_details = leaguepedia_parser.get_game_details(game)
            procesar_juego_leaguepedia(connection, game_details, torneo_id, nombre_torneo, indice_original)
            
        print(f"✅ Procesamiento completado. Nuevos registros: {len(nuevos_juegos)}")
        
    except Exception as e:
        connection.rollback()
        print(f"❌ Error crítico: {str(e)}")
    finally:
        cursor.close()
   

@sleep_and_retry
@limits(calls=18, period=90)
def procesar_juego_leaguepedia(connection, game_details, torneo_id, gamepedia_slug, index_gamepedia):
    cursor = connection.cursor(dictionary=True,buffered=True)
    
    try:
        # Generar ID compatible
        game_id = generate_leaguepedia_id(game_details)
        
        # Para el equipo azul
        blue_team_name = get_team_name_and_code_from_leaguepedia_team(game_details.teams.BLUE)
        team_blue_id = get_or_create_team_leaguepedia(connection, blue_team_name)
        add_team_to_team_tournament(connection, team_blue_id, torneo_id)

        # Para el equipo rojo
        red_team_name = get_team_name_and_code_from_leaguepedia_team(game_details.teams.RED)
        team_red_id = get_or_create_team_leaguepedia(connection, red_team_name)
        add_team_to_team_tournament(connection, team_red_id, torneo_id)

        # Crear/actualizar match (BO5)
        match_id = crear_match(
            connection,
            torneo_id,
            team_blue_id,
            team_red_id,
            game_details
        )
        
        # Insertar juego con gameInSeries
        insert_game(
            cursor, 
            game_id, 
            match_id,
            datetime.fromisoformat(game_details.start),
            game_details.gameInSeries,# Usar número de juego en la serie
            game_details.duration,
            game_details.patch,
            gamepedia_slug,
            index_gamepedia
        )
        
        # Procesar estadísticas de equipos
        procesar_estadisticas_equipo(
            cursor,
            game_id,
            team_blue_id,
            "blue",
            game_details.teams.BLUE,
            game_details.winner == "BLUE"
        )
        
        procesar_estadisticas_equipo(
            cursor,
            game_id,
            team_red_id,
            "red",
            game_details.teams.RED,
            game_details.winner == "RED"
        )
        
        # Procesar jugadores con mapeo de roles
        idx = 0
        for player in game_details.teams.BLUE.players:
            procesar_jugador_leaguepedia(
                cursor, 
                game_id, 
                player, 
                team_blue_id,
                idx
            )
            idx = idx + 1
            
        for player in game_details.teams.RED.players:
            procesar_jugador_leaguepedia(
                cursor, 
                game_id, 
                player, 
                team_red_id,
                idx
            )
            idx = idx + 1
        actualizar_resultados_match(cursor, match_id)
        connection.commit()
        print(f"✅ Juego {game_id} guardado (BO{game_details.gameInSeries})")
        
    except Exception as e:
        print(f"❌ Error procesando juego: {type(e).__name__}: {str(e)}")
        traceback.print_exc()  # Esto imprime la traza completa del error
        connection.rollback()
    finally:
        cursor.close()

def get_team_name_and_code_from_leaguepedia_team(team):
    """
    Dado un objeto LolGameTeam de Leaguepedia, devuelve (nombre_equipo)
    """
    # Nombre del equipo desde sources (Leaguepedia)
    team_name = getattr(team.sources.leaguepedia, 'name', None)
    return team_name

def get_or_create_team_leaguepedia(connection, team_name):
    cursor = connection.cursor(buffered=True)
    try:
        # Buscar por nombre
        cursor.execute("SELECT id FROM TEAM WHERE name LIKE %s", ('%' + team_name + '%',))        
        result = cursor.fetchone()
        if result:
            return result[0]

        # Obtener el último id
        cursor.execute("SELECT MAX(id) FROM team")
        last_id = cursor.fetchone()[0]
        if last_id is None:
            new_id = 1
        else:
            new_id = last_id + 1

        # Insertar nuevo equipo con nuevo id
        cursor.execute(
            "INSERT INTO TEAM (id, name) VALUES (%s, %s)",
            (new_id, team_name)
        )
        connection.commit()
        return new_id
    finally:
        cursor.close()

def actualizar_resultados_match(cursor, match_id):
    cursor.execute("""
        SELECT 
            m.team1_id,
            m.team2_id,
            SUM(CASE WHEN gs.team_id = m.team1_id AND gs.resultado = 1 THEN 1 ELSE 0 END) AS team1_wins,
            SUM(CASE WHEN gs.team_id = m.team2_id AND gs.resultado = 1 THEN 1 ELSE 0 END) AS team2_wins
        FROM MATCHES m
        LEFT JOIN GAME g ON g.match_id = m.id
        LEFT JOIN GAME_STATS gs ON g.id = gs.game_id 
        WHERE m.id = %s
        GROUP BY m.id, m.team1_id, m.team2_id
    """, (match_id,))
    result = cursor.fetchone()
    if result is None:
        team1_wins = team2_wins = 0
        team1_id = team2_id = None
    else:
        team1_id = result['team1_id']
        team2_id = result['team2_id']
        team1_wins = int(result['team1_wins'] or 0)
        team2_wins = int(result['team2_wins'] or 0)


    max_wins = max(team1_wins, team2_wins)
    strategy_count = 5 if max_wins >= 3 else 3 if max_wins == 2 else 1

    cursor.execute("""
        UPDATE MATCHES
        SET team1_result = %s,
            team2_result = %s,
            strategy_count = %s
        WHERE id = %s
    """, (team1_wins, team2_wins, strategy_count, match_id))

def map_leaguepedia_role(lp_role):
    """Mapea roles de Leaguepedia a los de la base de datos"""
    role_mapping = {
        'TOP': 'top',
        'JGL': 'jungle', 
        'MID': 'mid',
        'BOT': 'bottom',
        'SUP': 'support'
    }
    return role_mapping.get(lp_role, 'UNKNOWN')

def obtener_nombre_equipo_por_jugadores(players):
    """Extrae el nombre del equipo a partir de los datos de los jugadores"""
    # Implementación básica - en un caso real podrías buscar nombres oficiales de equipo
    roles = sorted([p.role for p in players if hasattr(p, "role")])
    return f"Team-{hash(''.join(roles))}"

def get_or_create_team_by_name(connection, team_name):
    """Busca o crea un equipo por su nombre y devuelve su ID"""
    cursor = connection.cursor(buffered=True)
    try:
        # Buscar equipo existente
        cursor.execute("SELECT id FROM TEAM WHERE name = %s", (team_name,))
        result = cursor.fetchone()
        if result:
            return result[0] if isinstance(result, tuple) else result["id"]
        
        # Crear código de equipo a partir del nombre
        team_code = ''.join([word[0] for word in team_name.split() if word])[:3].upper()
        
        # Insertar nuevo equipo
        cursor.execute(
            "INSERT INTO TEAM (code, name) VALUES (%s, %s)",
            (team_code, team_name)
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        cursor.close()

def generate_leaguepedia_id(game_details):
    """Genera ID único para juegos de Leaguepedia como entero"""
    timestamp = int(datetime.fromisoformat(game_details.start).timestamp())
    winner_hash = abs(hash(game_details.winner))  # Valor absoluto para evitar negativos
    # Tomar los primeros 6 dígitos del hash
    winner_hash_digits = int(str(winner_hash)[:6])
    # Concatenar timestamp y hash en un solo número
    leaguepedia_id = int(f"{timestamp}{winner_hash_digits}")
    return leaguepedia_id

def procesar_estadisticas_equipo(cursor, game_id, team_id, side, team_data, is_winner):
    """Procesa y guarda las estadísticas de un equipo"""
    # Extraer estadísticas
    kills = sum(p.endOfGameStats.kills for p in team_data.players 
                if hasattr(p, "endOfGameStats") and hasattr(p.endOfGameStats, "kills"))
    
    # Obtener estadísticas de estructuras y objetivos
    towers = 0
    inhibitors = 0
    barons = 0
    dragons = []
    
    if hasattr(team_data, "endOfGameStats"):
        stats = team_data.endOfGameStats
        towers = stats.turretKills if hasattr(stats, "turretKills") else 0
        barons = stats.baronKills if hasattr(stats, "baronKills") else 0
        num_dragons = stats.dragonKills if hasattr(stats, "dragonKills") else 0
        dragons = ["drake"] * num_dragons 
    
    # Calcular oro total
    total_gold = sum(p.endOfGameStats.gold for p in team_data.players 
                    if hasattr(p, "endOfGameStats") and hasattr(p.endOfGameStats, "gold"))
    
    # Crear objeto de estadísticas
    stats = {
        "totalGold": total_gold,
        "inhibitors": inhibitors,
        "towers": towers,
        "barons": barons,
        "totalKills": kills,
        "dragons": dragons
    }
    
    # Insertar estadísticas
    insert_game_stats(cursor, game_id, team_id, side, stats, side if is_winner else None)

def procesar_jugador_leaguepedia(cursor, game_id, player_data, team_id, participant_idx):
    """Procesa y guarda los datos de un jugador"""
    # Determinar nombre del jugador (en datos reales, debería estar disponible)
    role = map_leaguepedia_role(player_data.role)
    player_name = getattr(getattr(getattr(player_data, "sources", {}), "leaguepedia", {}), "name", None)    
    # Obtener o crear jugador
    player_id = get_or_create_player(cursor, player_name, participant_idx + 1, team_id)
    
    champion_id = get_champion_id(cursor, player_data.championName)
    
    # Extraer estadísticas
    if hasattr(player_data, "endOfGameStats"):
        stats = player_data.endOfGameStats
        participant_data = {
            'kills': stats.kills if hasattr(stats, "kills") else 0,
            'deaths': stats.deaths if hasattr(stats, "deaths") else 0,
            'assists': stats.assists if hasattr(stats, "assists") else 0,
            'participantId': participant_idx + 1,  # No disponible directamente
            'totalGold': stats.gold if hasattr(stats, "gold") else 0,
            'creepScore': stats.cs if hasattr(stats, "cs") else 0
        }
    else:
        participant_data = {
            'kills': 0, 'deaths': 0, 'assists': 0,
            'participantId': 0, 'totalGold': 0, 'creepScore': 0
        }
    
    # Insertar participante
    insert_participant(cursor, game_id, player_id, team_id, champion_id, participant_data)