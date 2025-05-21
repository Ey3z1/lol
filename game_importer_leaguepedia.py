from datetime import datetime, timedelta
import leaguepedia_parser
from game_insert import  get_or_create_player, get_champion_id, insert_game_stats, insert_participant, insert_game, crear_o_actualizar_match
from datetime import timedelta
from ratelimit import limits, sleep_and_retry

# Configuración de la base de datos
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Rodriguez123",
    "database": "league"
}

def procesar_torneo_leaguepedia(connection, torneo_id, nombre_torneo):
    """
    Procesa un torneo completo de Leaguepedia y guarda sus datos en la base de datos.
    
    Args:
        connection: Conexión a la base de datos MySQL
        torneo_id: ID del torneo en nuestra base de datos
        nombre_torneo: Nombre del torneo en formato Leaguepedia (ej. "LPL/2025 Season/Split 2")
    """
    cursor = connection.cursor(dictionary=True)
    
    try:
        print(f"\n🏆 Procesando torneo {nombre_torneo} desde Leaguepedia")
        
        # Obtener todos los juegos del torneo
        games = leaguepedia_parser.get_games(nombre_torneo)
        print(f"🎮 Encontrados {len(games)} juegos en Leaguepedia")
        
        for i, game in enumerate(games):
            print(f"\n    🕹️ Procesando juego {i+1}/{len(games)}")
            tournament = leaguepedia_parser.get_tournaments("China", 2025)

            # Obtener detalles completos del juego
            game_details = leaguepedia_parser.get_game_details(game, add_page_id=True)
            
            # Procesar y guardar el juego en la base de datos
            procesar_juego_leaguepedia(connection, game_details, torneo_id)
            
        print(f"✅ Procesamiento del torneo {nombre_torneo} completado")
        
    except Exception as e:
        print(f"❌ Error procesando torneo: {str(e)}")
    finally:
        cursor.close()        

@sleep_and_retry
@limits(calls=28, period=80)
def procesar_juego_leaguepedia(connection, game_details, torneo_id):
    cursor = connection.cursor(dictionary=True,buffered=True)
    
    try:
        # Generar ID compatible
        game_id = generate_leaguepedia_id(game_details)
        
        # Para el equipo azul
        blue_team_name = get_team_name_and_code_from_leaguepedia_team(game_details.teams.BLUE)
        team_blue_id = get_or_create_team_leaguepedia(connection, blue_team_name)

        # Para el equipo rojo
        red_team_name = get_team_name_and_code_from_leaguepedia_team(game_details.teams.RED)
        team_red_id = get_or_create_team_leaguepedia(connection, red_team_name)
        
        # Crear/actualizar match (BO5)
        match_id = crear_o_actualizar_match(
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
            game_details.patch    
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
        print(f"❌ Error procesando juego: {str(e)}")
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
    cursor = connection.cursor()
    try:
        # Buscar por nombre
        cursor.execute("SELECT id FROM team WHERE name LIKE %s", ('%' + team_name + '%',))        
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
            "INSERT INTO team (id, name) VALUES (%s, %s)",
            (new_id, team_name)
        )
        connection.commit()
        return new_id
    finally:
        cursor.close()

def actualizar_resultados_match(cursor, match_id):
    # Obtener todos los games y sus ganadores para el match dado
    cursor.execute("""
        SELECT 
            g.id AS game_id,
            gs.team_id,
            gs.resultado
        FROM game g
        JOIN game_stats gs ON g.id = gs.game_id
        WHERE g.match_id = %s AND gs.resultado IS NOT NULL
    """, (match_id,))
    rows = cursor.fetchall()

    # Obtener los equipos del match
    cursor.execute("""
        SELECT team1_id, team2_id FROM `match` WHERE id = %s
    """, (match_id,))
    team1_id, team2_id = cursor.fetchone()

    # Inicializar contadores de victorias
    team1_wins = 0
    team2_wins = 0

    # Contar victorias para cada equipo
    for game_id, team_id, resultado in rows:
        # El equipo con 'resultado' es el ganador
        if resultado and team_id == team1_id:
            team1_wins += 1
        elif resultado and team_id == team2_id:
            team2_wins += 1

    # Calcular el formato Best-Of
    max_wins = max(team1_wins, team2_wins)
    if max_wins >= 3:
        strategy_count = 5
    elif max_wins == 2:
        strategy_count = 3
    else:
        strategy_count = 1

    # Actualizar el match
    cursor.execute("""
        UPDATE `match`
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
    cursor = connection.cursor()
    try:
        # Buscar equipo existente
        cursor.execute("SELECT id FROM team WHERE name = %s", (team_name,))
        result = cursor.fetchone()
        if result:
            return result[0] if isinstance(result, tuple) else result["id"]
        
        # Crear código de equipo a partir del nombre
        team_code = ''.join([word[0] for word in team_name.split() if word])[:3].upper()
        
        # Insertar nuevo equipo
        cursor.execute(
            "INSERT INTO team (code, name) VALUES (%s, %s)",
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
    player_id = get_or_create_player(cursor, player_name, participant_idx + 1)
    
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