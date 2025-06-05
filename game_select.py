import mysql.connector
from datetime import datetime, timedelta
from config_local import DB_CONFIG, API_KEY

HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://lolesports.com"
}

def obtener_torneo_por_id(torneo_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, slug as name
        FROM TOURNAMENT
        WHERE id = %s
    """, (torneo_id,))
    torneo = cursor.fetchone()
    cursor.close()
    connection.close()
    return torneo

def obtener_matches_por_torneo(torneo_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            m.id as id,
            CONCAT(t1.name, ' - ', t2.name) as description,
            t1.image AS team1_image,
            t2.image AS team2_image,
            t1.name AS team1_name,
            t2.name AS team2_name,
            # Añadir conteo de victorias para mostrar resultados
            m.team1_result,
            m.team2_result
        FROM `MATCH` m
        JOIN TEAM t1 ON m.team1_id = t1.id
        JOIN TEAM t2 ON m.team2_id = t2.id
        WHERE m.tournamentId = %s
        ORDER BY start_time DESC
    """, (torneo_id,))
    
    matches = cursor.fetchall()
    cursor.close()
    connection.close()
    return matches

def obtener_games_por_match(match_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
           SELECT 
    g.id AS game_id,
    g.game_num,
    COALESCE(t_blue.name, 'Por definir') AS team_blue,
    COALESCE(t_red.name, 'Por definir') AS team_red,
    MAX(CASE WHEN gs.side = 'BLUE' THEN gs.resultado ELSE '0' END) AS resultado_blue,
    MAX(CASE WHEN gs.side = 'RED' THEN gs.resultado ELSE '0' END) AS resultado_red,
    CASE 
        WHEN MAX(CASE WHEN gs.side = 'BLUE' THEN gs.resultado END) = '1' THEN t_blue.name
        WHEN MAX(CASE WHEN gs.side = 'RED' THEN gs.resultado END) = '1' THEN t_red.name
        ELSE 'En juego'
    END AS winner,
    (
        SELECT GROUP_CONCAT(
            CONCAT(
                '<div class="player blue">',
                '<img src="', c.img, '" class="champion-img" title="', c.name, '">',
                '<div class="player-info">',
                    '<span class="player-name">', sp.name, '</span>',
                    '<span class="stats">',
                        '<span class="kda">', COALESCE(p.kills,0), '/', COALESCE(p.deaths,0), '/', COALESCE(p.assists,0), '</span>',
                        '<span class="cs">', COALESCE(p.creep_score,0), ' CS</span>',
                    '</span>',
                '</div></div>'
            ) ORDER BY p.num_participant SEPARATOR ''
        )
        FROM PARTICIPANT p
        JOIN SPORTS_PLAYER sp ON p.player_id = sp.id
        JOIN CHAMPION c ON p.champion_id = c.id
        WHERE p.game_id = g.id AND p.team_id = gs_blue.team_id
    ) AS blue_players,
    (
        SELECT GROUP_CONCAT(
            CONCAT(
                '<div class="player red">',
                '<img src="', c.img, '" class="champion-img" title="', c.name, '">',
                '<div class="player-info">',
                    '<span class="player-name">', sp.name, '</span>',
                    '<span class="stats">',
                        '<span class="kda">', COALESCE(p.kills,0), '/', COALESCE(p.deaths,0), '/', COALESCE(p.assists,0), '</span>',
                        '<span class="cs">', COALESCE(p.creep_score,0), ' CS</span>',
                    '</span>',
                '</div></div>'
            ) ORDER BY p.num_participant SEPARATOR ''
        )
        FROM PARTICIPANT p
        JOIN SPORTS_PLAYER sp ON p.player_id = sp.id
        JOIN CHAMPION c ON p.champion_id = c.id
        WHERE p.game_id = g.id AND p.team_id = gs_red.team_id
    ) AS red_players
FROM GAME g
LEFT JOIN GAME_STATS gs_blue 
    ON g.id = gs_blue.game_id 
    AND gs_blue.side = 'BLUE'
LEFT JOIN GAME_STATS gs_red 
    ON g.id = gs_red.game_id 
    AND gs_red.side = 'RED'
LEFT JOIN TEAM t_blue 
    ON gs_blue.team_id = t_blue.id
LEFT JOIN TEAM t_red 
    ON gs_red.team_id = t_red.id
LEFT JOIN GAME_STATS gs 
    ON g.id = gs.game_id
WHERE g.match_id = %s
GROUP BY g.id, g.game_num, t_blue.name, t_red.name
ORDER BY g.game_num;

        """, (match_id,))
        
        return cursor.fetchall()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()

def obtener_match_por_id(match_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, description 
        FROM `MATCH` 
        WHERE id = %s
        ORDER BY start_time desc
    """, (match_id,))
    match = cursor.fetchone()
    cursor.close()
    connection.close()
    return match

def obtener_equipos_con_imagen():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, code, image 
        FROM TEAM 
        ORDER BY name
    """)
    equipos = cursor.fetchall()
    cursor.close()
    connection.close()
    return equipos

def obtener_champions_con_imagen():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, img as image 
        FROM CHAMPION 
        ORDER BY name
    """)
    champions = cursor.fetchall()
    cursor.close()
    connection.close()
    return champions

def obtener_campeon_por_id(champion_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, img
        FROM CHAMPION where id = %s
    """, (champion_id,))
    CHAMPION = cursor.fetchone()
    cursor.close()
    connection.close()
    return champion


def obtener_equipos_para_select():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, code, image 
        FROM TEAM 
        ORDER BY name
    """)
    equipos = cursor.fetchall()
    cursor.close()
    connection.close()
    return equipos

def obtener_jugadores_por_equipos(team1_id, team2_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                p.player_id AS id,
                sp.name AS nickname,
                sp.role,
                t.name AS team_name,
                t.image AS team_image,
                t.id AS team_id,
                ROUND(AVG(p.kills), 1) AS avg_kills,
                COUNT(p.id) AS total_games
            FROM PARTICIPANT p
            JOIN SPORTS_PLAYER sp ON p.player_id = sp.id
            JOIN TEAM t ON p.team_id = t.id
            WHERE p.team_id IN (%s, %s)
            GROUP BY p.player_id, sp.name, sp.role, t.name, t.image
            ORDER BY 
                FIELD(p.team_id, %s, %s),
                CASE LOWER(sp.role)
                    WHEN 'top' THEN 1
                    WHEN 'jungle' THEN 2
                    WHEN 'mid' THEN 3
                    WHEN 'bottom' THEN 4
                    WHEN 'support' THEN 5
                    ELSE 6
                END
        """, (team1_id, team2_id, team1_id, team2_id))
        
        jugadores = cursor.fetchall()
        
        # Formatear decimales y asegurar valores
        for jugador in jugadores:
            jugador['avg_kills'] = float(jugador['avg_kills'] or 0)
        
        return jugadores
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()

# def obtener_jugadores_con_estadisticas(team1_id, team2_id):
#     connection = mysql.connector.connect(**DB_CONFIG)
#     cursor = connection.cursor(dictionary=True)
    
#     try:
#         cursor.execute("""
#             SELECT 
#                 p.player_id,
#                 sp.name AS nickname,
#                 p.role,
#                 t.name AS team_name,
#                 AVG(p.kills) AS avg_kills,
#                 JSON_ARRAYAGG(
#                     JSON_OBJECT(
#                         'fecha', m.start_time,
#                         'kills', p.kills,
#                         'resultado', m.team1_result
#                     )
#                 ) AS partidas
#             FROM PARTICIPANT p
#             JOIN SPORTS_PLAYER sp ON p.player_id = sp.id
#             JOIN TEAM t ON p.team_id = t.id
#             JOIN `MATCH` m ON p.match_id = m.id
#             WHERE t.id IN (%s, %s)
#             GROUP BY p.player_id
#         """, (team1_id, team2_id))
        
#         jugadores = cursor.fetchall()
        
#         # Parsear JSON de partidas
#         for jugador in jugadores:
#             jugador['partidas'] = json.loads(jugador['partidas'])
#             jugador['linea'] = obtener_linea_actual(jugador['player_id'])  # Función que debes implementar
            
#         return jugadores
        
#     finally:
#         cursor.close()
#         connection.close()

def obtener_jugador_por_id(jugador_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            p.player_id,
            sp.name AS nickname,
            t.name AS team_name,
            t.id AS team_id,
            sp.role
        FROM PARTICIPANT p
        JOIN SPORTS_PLAYER sp ON p.player_id = sp.id
        JOIN TEAM t ON p.team_id = t.id
        WHERE p.player_id = %s
    """, (jugador_id,))
    
    return cursor.fetchone()

def obtener_partidas_jugador(player_id, bans):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Generar placeholders dinámicamente
        if bans:
            ban_placeholders = ','.join(['%s'] * len(bans))
            query = f"""
                SELECT
                    g.id AS game_id,
                    g.game_num,
                    g.start_time AS fecha,
                    p.kills,
                    CASE WHEN gs.resultado = 1 THEN TRUE ELSE FALSE END AS resultado,
                    c.img AS champion_img,
                    c.name AS champion_name,
                    t.name AS equipo_jugador,
                    t_oponente.name AS equipo_oponente
                FROM PARTICIPANT p
                JOIN GAME g ON p.game_id = g.id
                JOIN GAME_STATS gs ON g.id = gs.game_id AND p.team_id = gs.team_id
                JOIN CHAMPION c ON p.champion_id = c.id
                JOIN TEAM t ON gs.team_id = t.id
                JOIN GAME_STATS gs_oponente 
                    ON g.id = gs_oponente.game_id 
                    AND gs_oponente.team_id != gs.team_id
                JOIN TEAM t_oponente ON gs_oponente.team_id = t_oponente.id
                JOIN `MATCH` m ON m.id = g.match_id
                JOIN tournament tt on tt.id = m.tournamentId
                WHERE p.player_id = %s 
                    AND tt.activo = 1 
                    AND c.id NOT IN ({ban_placeholders})
                ORDER BY g.start_time DESC
            """
            
            # Combinar parámetros: player_id + lista de bans
            params = [player_id] + list(bans)
            cursor.execute(query, params)
        else:
            # Si no hay bans, ejecutar consulta sin filtro de campeones
            query = """
                SELECT
                    g.id AS game_id,
                    g.game_num,
                    g.start_time AS fecha,
                    p.kills,
                    CASE WHEN gs.resultado = 1 THEN TRUE ELSE FALSE END AS resultado,
                    c.img AS champion_img,
                    c.name AS champion_name,
                    t.name AS equipo_jugador,
                    t_oponente.name AS equipo_oponente
                FROM PARTICIPANT p
                JOIN GAME g ON p.game_id = g.id
                JOIN GAME_STATS gs ON g.id = gs.game_id AND p.team_id = gs.team_id
                JOIN CHAMPION c ON p.champion_id = c.id
                JOIN TEAM t ON gs.team_id = t.id
                JOIN GAME_STATS gs_oponente 
                    ON g.id = gs_oponente.game_id 
                    AND gs_oponente.team_id != gs.team_id
                JOIN TEAM t_oponente ON gs_oponente.team_id = t_oponente.id
                JOIN `MATCH` m ON m.id = g.match_id
                JOIN tournament tt on tt.id = m.tournamentId
                WHERE p.player_id = %s AND tt.activo = 1
                ORDER BY g.start_time DESC
            """
            cursor.execute(query, (player_id,))
            
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def obtener_max_index_leaguepedia(connection, torneo_id):
    """Retorna el máximo index_leaguepedia registrado para el torneo"""
    cursor = connection.cursor()
    try:
        query = """
        SELECT COALESCE(MAX(index_leaguepedia), 0) 
        FROM game 
        WHERE leaguepedia_slug = %s
        """
        cursor.execute(query, (torneo_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Error obteniendo máximo índice: {str(e)}")
        return 0
    finally:
        cursor.close()