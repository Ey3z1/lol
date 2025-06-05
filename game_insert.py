import mysql.connector
from datetime import datetime, timedelta
import time
import hashlib
from config_local import DB_CONFIG


def get_or_create_player(cursor, player_name, participant_id, team_id):
    cursor.execute("SELECT id FROM SPORTS_PLAYER WHERE name like %s  and team_id = %s ", ('%' + player_name, team_id,))
    player = cursor.fetchone()
    
    if player:
        return player["id"]  # Acceso por nombre de columna
    
    # Determinar el rol según participant_id
    if participant_id in [1, 6]:
        role = 'top'
    elif participant_id in [2, 7]:
        role = 'jungle'
    elif participant_id in [3, 8]:
        role = 'mid'
    elif participant_id in [4, 9]:
        role = 'bottom'
    elif participant_id in [5, 10]:
        role = 'support'
    else:
        role = None  # O puedes manejar el error según tu lógica

    # Insertar el jugador con el rol directamente
    code = get_team_code_by_id(cursor, team_id)
    if code in player_name:
        name = player_name
    else:
        name = code + ' ' + player_name
    cursor.execute(
        "INSERT INTO SPORTS_PLAYER (name, role, team_id) VALUES (%s, %s, %s)",
        (name, role, team_id)
    )
    return cursor.lastrowid

def insert_game(cursor, game_id, match_id, start_time, game_num, duration, patch, leaguepedia_slug, index_leaguepedia):
    from datetime import datetime

    # Si start_time es string, conviértelo a datetime
    if isinstance(start_time, str):
        start_time_clean = start_time.rstrip('Z')
        try:
            dt = datetime.fromisoformat(start_time_clean)
        except ValueError:
            dt = datetime.strptime(start_time_clean, "%Y-%m-%dT%H:%M:%S")
        mysql_datetime = dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # DATETIME(3)
    else:
        mysql_datetime = start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    cursor.execute(
        """
        INSERT INTO GAME (id, match_id, start_time, game_num, duration, patch, leaguepedia_slug, index_leaguepedia) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            match_id = VALUES(match_id), 
            start_time = VALUES(start_time),
            game_num = VALUES(game_num),
            duration = VALUES(duration),
            patch = VALUES(patch),
            leaguepedia_slug = VALUES(leaguepedia_slug),
            index_leaguepedia = VALUES(index_leaguepedia)
        """,
        (game_id, match_id, mysql_datetime, game_num, duration, patch, leaguepedia_slug, index_leaguepedia)
    )

def insert_game_stats(cursor, game_id, team_id, side, stats, resultado):
    cursor.execute(
        """
        INSERT INTO GAME_STATS (game_id, team_id, side, total_gold, inhibitors, towers, barons, total_kills, total_dragons, resultado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            game_id, team_id, side, stats["totalGold"], stats["inhibitors"],
            stats["towers"], stats["barons"], stats["totalKills"], len(stats["dragons"]),1 if resultado == side else (0 if resultado is None else 0)

        )
    )

def insert_participant(cursor, game_id, player_id, team_id, champion_id, data):
    cursor.execute("""
        INSERT INTO PARTICIPANT 
        (game_id, player_id, team_id, champion_id, kills, deaths, assists, num_participant, total_gold, creep_score)
         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        game_id,
        player_id,
        team_id,
        champion_id,
        data.get('kills', 0),
        data.get('deaths', 0),
        data.get('assists', 0),
        data.get('participantId', 0),
        data.get('totalGold', 0),
        data.get('creepScore', 0)
    ))

def get_formatted_starting_time():
    now = datetime.utcnow() - timedelta(seconds=30)
    rounded_seconds = int(time.mktime(now.timetuple()) // 10 * 10)
    return datetime.utcfromtimestamp(rounded_seconds).isoformat() + "Z"

def get_team_code_from_participant(participant):
    """Extrae el código del equipo del summonerName del primer participante."""
    name = participant.get('summonerName', '')
    if name:
        return name.split()[0].upper()
    return None

def get_team_id_by_code(cursor, team_code):
    """Obtiene el team_id usando el código extraído"""
    cursor.execute(
        "SELECT id FROM TEAM WHERE code = %s",
        (team_code,)
    )
    result = cursor.fetchone()
    if result is None:
        return None
    # Si fetchone() devuelve un diccionario:
    if isinstance(result, dict):
        return result.get("id")
    # Si fetchone() devuelve una tupla:
    return result[0]

def get_team_code_by_id(cursor, team_id):
    """Obtiene el código del equipo usando el team_id"""
    cursor.execute(
        "SELECT code FROM TEAM WHERE id = %s",
        (team_id,)
    )
    result = cursor.fetchone()
    if result is None:
        return None
    # Si fetchone() devuelve un diccionario:
    if isinstance(result, dict):
        return result.get("code")
    # Si fetchone() devuelve una tupla:
    return result[0]

def get_champion_id(cursor, champion_code):
    """Obtiene el ID del campeón (lo crea si no existe), eliminando espacios y comillas simples"""
    try:
        # Limpiar el código: eliminar todos los espacios y comillas simples
        clean_code = champion_code.replace("Wukong", "MonkeyKing").replace("Renata Glasc", "Renata").replace(' ', '').replace("'", "").replace("RenataGlasc", "Renata")
        
        # Intentar insertar el campeón (IGNORE evita errores si ya existe)
        cursor.execute(
            "INSERT IGNORE INTO CHAMPION (name, img) VALUES (%s, %s)",
            (
                clean_code,
                'https://ddragon.leagueoflegends.com/cdn/15.9.1/img/champion/' + clean_code + '.png'
            )
        )
        
        # Obtener el ID recién creado (si se insertó)
        if cursor.lastrowid != 0:
            return cursor.lastrowid
        
        # Si no se insertó (ya existía), buscamos el ID existente
        cursor.execute(
            "SELECT id FROM CHAMPION WHERE name = %s",
            (clean_code,)
        )
        result = cursor.fetchone()
        return result['id'] if result else None
        
    except Exception as e:
        print(f"⚠ Error en get_champion_id({champion_code}): {str(e)}")
        return None

def obtener_torneos_de_bbdd():
    current_year = datetime.now().year  # Esto será 2025
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, slug as name
        FROM TOURNAMENT
        WHERE slug LIKE %s
        ORDER BY id DESC
    """, (f"%{current_year}%",))
    torneos = cursor.fetchall()
    cursor.close()
    connection.close()
    return torneos

def obtener_torneos_con_matches_de_bbdd():
    current_year = datetime.now().year  # Esto será 2025
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT t.id, t.slug as name
        FROM TOURNAMENT t
        JOIN `MATCH` m ON t.id = m.tournamentId
        WHERE t.slug LIKE %s
        ORDER BY t.id DESC
    """, (f"%{current_year}%",))
    torneos = cursor.fetchall()
    cursor.close()
    connection.close()
    return torneos

def get_or_create_team(team_code, team_name, team_image, connection):
    cur = connection.cursor()
    cur.execute("SELECT id FROM TEAM WHERE code = %s", (team_code,))
    row = cur.fetchone()
    if row:
        team_id = row[0]
    else:
        cur.execute(
            "INSERT INTO TEAM (code, name, image) VALUES (%s, %s, %s)",
            (team_code, team_name, team_image)
        )
        connection.commit()
        team_id = cur.lastrowid
    cur.close()
    return team_id

def get_or_create_match(match_id, tournament_id, strategy_type, strategy_count, team1_result, team2_result,
                        team1_id, team2_id, block_name, start_time, connection):
    cur = connection.cursor()
    cur.execute("SELECT id FROM `MATCH` WHERE id = %s", (match_id,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]
    cur.execute("""
        INSERT INTO `MATCH`
        (id, tournamentId, strategy_type, strategy_count, team1_result, team2_result, team1_id, team2_id,
         block_name, start_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (match_id, tournament_id, strategy_type, strategy_count, team1_result, team2_result,
          team1_id, team2_id, block_name, start_time))
    connection.commit()
    cur.close()
    return match_id

def get_league_id(league_name, connection):
    if not league_name:
        return None
    cur = connection.cursor()
    try:
        cur.execute("SELECT id FROM LEAGUE WHERE name = %s", (league_name,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()

def parse_iso_time(iso_string):
    from datetime import datetime
    if not iso_string:
        return None
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error parsing ISO time '{iso_string}': {e}")
        return None

def determine_winner(frame):
    blue = frame["blueTeam"]
    red = frame["redTeam"]
    
    blue_wins = blue["inhibitors"] >= 1 and blue["towers"] >= 5
    red_wins = red["inhibitors"] >= 1 and red["towers"] >= 5
    
    if blue_wins and not red_wins:
        return "blue"
    elif red_wins and not blue_wins:
        return "red"
    else:
        return None
    
def ajustar_games_match(conn, match_id):
    cursor = conn.cursor()
    pendientes = 0  # Valor predeterminado
    match_id = match_id['id'] if isinstance(match_id, dict) else match_id
    try:
        # Verificar si hay juegos sin resultado para el match
        print(f"Verificando juegos sin resultado para el match {match_id}...")
        cursor.execute('''
            SELECT COUNT(*)
            FROM GAME g
            JOIN `MATCH` m ON g.match_id = m.id
            LEFT JOIN GAME_STATS gs1 ON gs1.game_id = g.id AND gs1.team_id = m.team1_id
            LEFT JOIN GAME_STATS gs2 ON gs2.game_id = g.id AND gs2.team_id = m.team2_id
            WHERE g.match_id = %s
            AND ((gs1.resultado IS NULL OR gs1.resultado = 0) AND (gs2.resultado IS NULL OR gs2.resultado = 0))
        ''', (match_id,))
        resultado = cursor.fetchone()
        pendientes = resultado[0] if resultado else 0  # Si no hay resultados, usa 0
        if pendientes == 0:
            print(f"No hay juegos pendientes de resultado para el match {match_id}.")
            return

        # Obtener información del match específico
        print(f"Obteniendo información del match {match_id}...")
        cursor.execute("SELECT team1_id, team2_id, team1_result, team2_result FROM `MATCH` WHERE id = %s", (match_id,))
        match = cursor.fetchone()
        if not match:
            print(f"No se encontró el match con id {match_id}.")
            return

        team1_id = int(match[0])
        team2_id = int(match[1])
        team1_result = int(match[2])
        team2_result = int(match[3])

        # Contar juegos ganados por cada equipo
        print(f"Contando juegos ganados para team1 ({team1_id}) y team2 ({team2_id})...")
        cursor.execute('''SELECT COUNT(*) FROM GAME g
                          JOIN GAME_STATS gs ON g.id = gs.game_id
                          WHERE g.match_id = %s AND gs.team_id = %s AND gs.resultado = '1' ''', (match_id, team1_id))
        team1_games = cursor.fetchone()
        team1_games = team1_games[0] if team1_games else 0
        
        cursor.execute('''SELECT COUNT(*) FROM GAME g
                          JOIN GAME_STATS gs ON g.id = gs.game_id
                          WHERE g.match_id = %s AND gs.team_id = %s AND gs.resultado = '1' ''', (match_id, team2_id))
        team2_games = cursor.fetchone()
        team2_games = team2_games[0] if team2_games else 0

        print(f"Team1 ({team1_id}) tiene {team1_games} juegos ganados de {team1_result} esperados.")
        print(f"Team2 ({team2_id}) tiene {team2_games} juegos ganados de {team2_result} esperados.")
        
        # Ajustar resultados si hay juegos sin resultado
        if team1_games < team1_result:
            to_fix = team1_result - team1_games
            print(f"Ajustando {to_fix} juegos para team1 ({team1_id})...")

            # Selecciona solo los game_id donde AMBOS equipos tienen resultado NULL o 0
            cursor.execute('''
                SELECT g.id
                FROM GAME g
                JOIN GAME_STATS gs1 ON g.id = gs1.game_id AND gs1.team_id = %s
                JOIN GAME_STATS gs2 ON g.id = gs2.game_id AND gs2.team_id = %s
                WHERE g.match_id = %s
                AND (gs1.resultado IS NULL OR gs1.resultado = '0')
                AND (gs2.resultado IS NULL OR gs2.resultado = '0')
                ORDER BY g.id ASC
                LIMIT %s
            ''', (team1_id, team2_id, match_id, to_fix))
            target_games = [row[0] for row in cursor.fetchall()]

            if target_games:
                cursor.execute(f'''
                    UPDATE GAME_STATS gs
                    JOIN GAME g ON g.id = gs.game_id
                    SET gs.resultado = CASE 
                        WHEN gs.team_id = %s THEN '1' 
                        ELSE '0' 
                    END
                    WHERE g.id IN ({','.join(['%s']*len(target_games))})
                    AND gs.team_id IN (%s, %s)
                ''', (team1_id, *target_games, team1_id, team2_id))

        # Ajuste para team2
        if team2_games < team2_result:
            to_fix = team2_result - team2_games
            print(f"Ajustando {to_fix} juegos para team2 ({team2_id})...")

            cursor.execute('''
                SELECT g.id
                FROM GAME g
                JOIN GAME_STATS gs1 ON g.id = gs1.game_id AND gs1.team_id = %s
                JOIN GAME_STATS gs2 ON g.id = gs2.game_id AND gs2.team_id = %s
                WHERE g.match_id = %s
                AND (gs1.resultado IS NULL OR gs1.resultado = '0')
                AND (gs2.resultado IS NULL OR gs2.resultado = '0')
                ORDER BY g.id ASC
                LIMIT %s
            ''', (team2_id, team1_id, match_id, to_fix))
            target_games = [row[0] for row in cursor.fetchall()]

            if target_games:
                cursor.execute(f'''
                    UPDATE GAME_STATS gs
                    JOIN GAME g ON g.id = gs.game_id
                    SET gs.resultado = CASE 
                        WHEN gs.team_id = %s THEN '1' 
                        ELSE '0' 
                    END
                    WHERE g.id IN ({','.join(['%s']*len(target_games))})
                    AND gs.team_id IN (%s, %s)
                ''', (team2_id, *target_games, team2_id, team1_id))


        print(f"✅ Resultados ajustados correctamente para el match {match_id}.")
    except mysql.connector.Error as e:
        print(f"❌ Error de MySQL en el match {match_id}: {e}")
    except Exception as e:
        print(f"❌ Error inesperado en el match {match_id}: {e}")
    finally:
        cursor.close()

def generar_match_id(torneo_id, team1, team2, fecha):
    # Normalización de equipos (orden lexicográfico)
    equipo_min, equipo_max = sorted([str(team1)[-3:].zfill(3), 
                                    str(team2)[-3:].zfill(3)])
    
    # Semilla única basada en componentes invariantes
    semilla = f"{str(torneo_id)[-3:]}{equipo_min}{equipo_max}{fecha}"
    
    # Hashing criptográfico para unicidad garantizada
    hash_sha256 = hashlib.sha256(semilla.encode()).hexdigest()
    
    # Truncamiento seguro a 15 dígitos
    return int(hash_sha256[:15], 16)

def crear_match(connection, torneo_id, team_blue_id, team_red_id, game_details):
    cursor = connection.cursor()
    try:
        winner_team_id = team_blue_id if game_details.winner == 'BLUE' else team_red_id
        start_date = game_details.start[:10]
        match_id = generar_match_id(torneo_id, team_blue_id, team_red_id, start_date)
        # Convierte a formato compatible con MySQL
        dt = datetime.fromisoformat(game_details.start.replace('Z', '+00:00'))
        mysql_datetime = dt.strftime('%Y-%m-%d %H:%M:%S')
        # Buscar si ya existe el match
        cursor.execute("SELECT team1_result, team2_result, strategy_count FROM `MATCH` WHERE id = %s", (match_id,))
        row = cursor.fetchone()

        if not row:
            # Insertar nuevo match con best-of 1
            team1_result = 1 if winner_team_id == team_blue_id else 0
            team2_result = 1 if winner_team_id == team_red_id else 0
            strategy_count = 1
            cursor.execute("""
                INSERT INTO `MATCH`
                (id, tournamentId, strategy_type, strategy_count, team1_result, team2_result, team1_id, team2_id, start_time)
                VALUES (%s, %s, 'bestOf', %s, %s, %s, %s, %s, %s)
            """, (match_id, torneo_id, strategy_count, team1_result, team2_result, team_blue_id, team_red_id, mysql_datetime))

        connection.commit()
        return match_id
    finally:
        cursor.close()
        
def leaguepedia_match_id(torneo_id, team1_id, team2_id, fecha):
    """
    Genera un ID BIGINT único para un match de Leaguepedia.
    Usa un rango reservado alto para evitar colisiones.
    """
    # Por ejemplo: 10,AAAABBBBCCCDD (A=torneo, B=team1, C=team2, D=fecha)
    # Ajusta los multiplicadores según el rango de tus IDs reales
    base = 10_000_000_000_000  # Rango reservado para Leaguepedia
    tid = int(torneo_id) % 10_000    # 4 dígitos
    t1 = int(team1_id) % 10_000      # 4 dígitos
    t2 = int(team2_id) % 10_000      # 4 dígitos
    # Fecha en formato YYMMDD (6 dígitos)
    ymd = int(fecha.strftime("%y%m%d"))
    return base + tid * 10**10 + t1 * 10**6 + t2 * 10**2 + (ymd % 100)

# if __name__ == "__main__":
#     connection = None
#     try:
#         connection = mysql.connector.connect(**DB_CONFIG)
#         print("Conectado a la base de datos.")
#         importar_diferencial(connection)
#     except Exception as e:
#         print(f"❌ Error: {e}")
#     finally:
#         if connection is not None and connection.is_connected():
#             connection.close()
#             print("Conexión cerrada.")
