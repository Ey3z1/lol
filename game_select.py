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

def obtener_torneos_activos():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()
    cursor.execute("""
        SELECT id
        FROM TOURNAMENT
        WHERE activo = 1
    """)
    torneos_activos = [str(row[0]) for row in cursor.fetchall()]  # Convertir a string aquí
    cursor.close()
    connection.close()
    return torneos_activos



def obtener_clasificacion_torneo(torneo_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT
    t.id AS team_id,
    t.name AS team_name,
    t.image AS team_image,
    tt.tier AS tier,
    COUNT(DISTINCT m.id) AS matches_jugados,
    SUM(
      CASE
        WHEN (m.team1_id = t.id AND m.team1_result > m.team2_result)
          OR (m.team2_id = t.id AND m.team2_result > m.team1_result)
        THEN 1 ELSE 0 END
    ) AS matches_ganados,
    SUM(
      CASE
        WHEN (m.team1_id = t.id AND m.team1_result < m.team2_result)
          OR (m.team2_id = t.id AND m.team2_result < m.team1_result)
        THEN 1 ELSE 0 END
    ) AS matches_perdidos,

    -- Games jugados, ganados y perdidos usando subselects con COUNT(DISTINCT)
    (
      SELECT COUNT(DISTINCT gs.game_id)
      FROM game_stats gs
      JOIN game g ON g.id = gs.game_id
      WHERE gs.team_id = t.id
        AND g.match_id IN (
            SELECT id FROM matches WHERE tournament_id = tt.tournament_id
        )
    ) AS games_jugados,

    (
      SELECT COUNT(DISTINCT gs.game_id)
      FROM game_stats gs
      JOIN game g ON g.id = gs.game_id
      WHERE gs.team_id = t.id AND gs.resultado = 1
        AND g.match_id IN (
            SELECT id FROM matches WHERE tournament_id = tt.tournament_id
        )
    ) AS games_ganados,

    (
      SELECT COUNT(DISTINCT gs.game_id)
      FROM game_stats gs
      JOIN game g ON g.id = gs.game_id
      WHERE gs.team_id = t.id AND gs.resultado = 0
        AND g.match_id IN (
            SELECT id FROM matches WHERE tournament_id = tt.tournament_id
        )
    ) AS games_perdidos

FROM
    team_tournament tt
JOIN team t ON t.id = tt.team_id
LEFT JOIN matches m ON (
    (m.team1_id = t.id OR m.team2_id = t.id)
    AND m.tournament_id = tt.tournament_id
)
WHERE
    tt.tournament_id = %s
GROUP BY
    t.id, t.name, t.image, tt.tier
ORDER BY
    matches_ganados DESC, matches_perdidos ASC;

    """, (torneo_id,))
    clasificacion = cursor.fetchall()
    cursor.close()
    connection.close()
    return clasificacion

def obtener_stats_torneo(torneo_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
         WITH totales AS (
          SELECT
            g.id AS game_id,
            SUM(gs.towers)   AS towers,
            SUM(gs.total_kills)    AS kills,
            SUM(gs.total_dragons)  AS dragons,
            SUM(gs.barons)   AS barons
          FROM game g
          JOIN game_stats gs ON gs.game_id = g.id
          JOIN matches m ON m.id = g.match_id
          WHERE m.tournament_id = %s
          GROUP BY g.id
        )
        SELECT
          -- Medias por game
          ROUND(AVG(towers), 2)  AS media_torres,
          ROUND(AVG(kills), 2)   AS media_kills,
          ROUND(AVG(dragons), 2) AS media_dragones,
          ROUND(AVG(barons), 2)  AS media_barones,

          -- Over/Under torres
          SUM(CASE WHEN towers > 12.5 THEN 1 ELSE 0 END)         AS games_over_12_5_torres,
          SUM(CASE WHEN towers <= 12.5 THEN 1 ELSE 0 END)        AS games_under_eq_12_5_torres,
          SUM(CASE WHEN towers > 11.5 THEN 1 ELSE 0 END)         AS games_over_11_5_torres,
          SUM(CASE WHEN towers <= 11.5 THEN 1 ELSE 0 END)        AS games_under_eq_11_5_torres,
          SUM(CASE WHEN towers > 10.5 THEN 1 ELSE 0 END)         AS games_over_10_5_torres,
          SUM(CASE WHEN towers <= 10.5 THEN 1 ELSE 0 END)        AS games_under_eq_10_5_torres,

          -- Over/Under dragones
          SUM(CASE WHEN dragons > 4.5 THEN 1 ELSE 0 END)         AS games_over_4_5_dragones,
          SUM(CASE WHEN dragons <= 4.5 THEN 1 ELSE 0 END)        AS games_under_eq_4_5_dragones,

          -- Over thresholds kills
          SUM(CASE WHEN kills > 22.5 THEN 1 ELSE 0 END)          AS games_over_22_5_kills,
          SUM(CASE WHEN kills > 23.5 THEN 1 ELSE 0 END)          AS games_over_23_5_kills,
          SUM(CASE WHEN kills > 24.5 THEN 1 ELSE 0 END)          AS games_over_24_5_kills,
          SUM(CASE WHEN kills > 25.5 THEN 1 ELSE 0 END)          AS games_over_25_5_kills,
          SUM(CASE WHEN kills > 26.5 THEN 1 ELSE 0 END)          AS games_over_26_5_kills,
          SUM(CASE WHEN kills > 27.5 THEN 1 ELSE 0 END)          AS games_over_27_5_kills,
          SUM(CASE WHEN kills > 28.5 THEN 1 ELSE 0 END)          AS games_over_28_5_kills,
          SUM(CASE WHEN kills > 29.5 THEN 1 ELSE 0 END)          AS games_over_29_5_kills,
          SUM(CASE WHEN kills > 30.5 THEN 1 ELSE 0 END)          AS games_over_30_5_kills,
          SUM(CASE WHEN kills > 31.5 THEN 1 ELSE 0 END)          AS games_over_31_5_kills,
          SUM(CASE WHEN kills > 32.5 THEN 1 ELSE 0 END)          AS games_over_32_5_kills,


          -- Over/Under barones
          SUM(CASE WHEN barons > 1.5 THEN 1 ELSE 0 END)          AS games_over_1_5_barones,
          SUM(CASE WHEN barons <= 1.5 THEN 1 ELSE 0 END)         AS games_under_eq_1_5_barones

        FROM totales;
    """, (torneo_id,))
    stats = cursor.fetchone()
    cursor.close()
    connection.close()
    return stats

def obtener_stats_equipos(torneo_id):
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
         WITH participaciones AS (
    SELECT
        t.id         AS team_id,
        t.name       AS team_name,
        t.image     AS team_image,
        tt.tier      AS tier,
        tg.game_id,
        tg.dragons   AS dragons_totales,
        tg.towers    AS towers_totales,
        tg.barons    AS barons_totales,
        tg.kills     AS kills_totales
    FROM team_tournament tt
    JOIN team t ON t.id = tt.team_id
    JOIN matches m ON m.tournament_id = tt.tournament_id
        AND (m.team1_id = t.id OR m.team2_id = t.id)
    JOIN game g ON g.match_id = m.id
    JOIN totales_game tg ON tg.game_id = g.id
    WHERE tt.tournament_id = %s
    GROUP BY t.id, t.name, tt.tier, tg.game_id, tg.dragons, tg.towers, tg.barons, tg.kills
)
SELECT
    team_id,
    team_name,
    team_image,
    tier,
    -- Dragones 4.5
    COUNT(CASE WHEN dragons_totales > 4.5  THEN 1 END) AS dragons_over_4_5,
    COUNT(CASE WHEN dragons_totales <= 4.5 THEN 1 END) AS dragons_under_eq_4_5,
    -- Torres 12.5 y 11.5
    COUNT(CASE WHEN towers_totales > 12.5  THEN 1 END) AS towers_over_12_5,
    COUNT(CASE WHEN towers_totales <= 12.5 THEN 1 END) AS towers_under_eq_12_5,
    COUNT(CASE WHEN towers_totales > 11.5  THEN 1 END) AS towers_over_11_5,
    COUNT(CASE WHEN towers_totales <= 11.5 THEN 1 END) AS towers_under_eq_11_5,
    COUNT(CASE WHEN towers_totales > 10.5  THEN 1 END) AS towers_over_10_5,
    COUNT(CASE WHEN towers_totales <= 10.5 THEN 1 END) AS towers_under_eq_10_5,
    -- Barones 1.5
    COUNT(CASE WHEN barons_totales > 1.5  THEN 1 END) AS barons_over_1_5,
    COUNT(CASE WHEN barons_totales <= 1.5 THEN 1 END) AS barons_under_eq_1_5,
    -- Kills con distintos thresholds
    COUNT(CASE WHEN kills_totales > 22.5  THEN 1 END) AS kills_over_22_5,
    COUNT(CASE WHEN kills_totales <= 22.5 THEN 1 END) AS kills_under_eq_22_5,
    COUNT(CASE WHEN kills_totales > 23.5  THEN 1 END) AS kills_over_23_5,
    COUNT(CASE WHEN kills_totales <= 23.5 THEN 1 END) AS kills_under_eq_23_5,
    COUNT(CASE WHEN kills_totales > 24.5  THEN 1 END) AS kills_over_24_5,
    COUNT(CASE WHEN kills_totales <= 24.5 THEN 1 END) AS kills_under_eq_24_5,
    COUNT(CASE WHEN kills_totales > 25.5  THEN 1 END) AS kills_over_25_5,
    COUNT(CASE WHEN kills_totales <= 25.5 THEN 1 END) AS kills_under_eq_25_5,
    COUNT(CASE WHEN kills_totales > 26.5  THEN 1 END) AS kills_over_26_5,
    COUNT(CASE WHEN kills_totales <= 26.5 THEN 1 END) AS kills_under_eq_26_5,
    COUNT(CASE WHEN kills_totales > 27.5  THEN 1 END) AS kills_over_27_5,
    COUNT(CASE WHEN kills_totales <= 27.5 THEN 1 END) AS kills_under_eq_27_5,
    COUNT(CASE WHEN kills_totales > 28.5  THEN 1 END) AS kills_over_28_5,
    COUNT(CASE WHEN kills_totales <= 28.5 THEN 1 END) AS kills_under_eq_28_5,
    COUNT(CASE WHEN kills_totales > 29.5  THEN 1 END) AS kills_over_29_5,
    COUNT(CASE WHEN kills_totales <= 29.5 THEN 1 END) AS kills_under_eq_29_5,
    COUNT(CASE WHEN kills_totales > 30.5  THEN 1 END) AS kills_over_30_5,
    COUNT(CASE WHEN kills_totales <= 30.5 THEN 1 END) AS kills_under_eq_30_5,
    COUNT(CASE WHEN kills_totales > 31.5  THEN 1 END) AS kills_over_31_5,
    COUNT(CASE WHEN kills_totales <= 31.5 THEN 1 END) AS kills_under_eq_31_5,     
    COUNT(CASE WHEN kills_totales > 32.5  THEN 1 END) AS kills_over_32_5,
    COUNT(CASE WHEN kills_totales <= 32.5 THEN 1 END) AS kills_under_eq_32_5            
FROM participaciones
GROUP BY team_id, team_name, tier
ORDER BY team_name;

    """, (torneo_id,))
    stats = cursor.fetchall()
    cursor.close()
    connection.close()
    return stats

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
        FROM MATCHES m
        JOIN TEAM t1 ON m.team1_id = t1.id
        JOIN TEAM t2 ON m.team2_id = t2.id
        WHERE m.tournament_id = %s
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
        FROM MATCHES 
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
    champion = cursor.fetchone()
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
            WHERE p.team_id IN (%s, %s) and activo=1
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
#             JOIN MATCHES m ON p.match_id = m.id
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
        WITH partidas_activos AS (
            SELECT p.game_id, gs.resultado, p.kills
            FROM participant p
            JOIN game_stats gs ON gs.game_id = p.game_id AND gs.team_id = p.team_id
            JOIN game g ON g.id = p.game_id
            JOIN matches m ON m.id = g.match_id
            JOIN tournament t ON t.id = m.tournament_id
            WHERE t.activo = 1 AND p.player_id = %s
        ),
        top_kills_info AS (
            SELECT 
                pa.game_id,
                pa.resultado,
                pa.kills,
                (SELECT MAX(kills) FROM participant WHERE game_id = pa.game_id) AS max_kills,
                (SELECT COUNT(*) FROM participant WHERE game_id = pa.game_id AND kills = pa.kills) AS count_equal_kills
            FROM partidas_activos pa
        )
        SELECT 
            sp.id AS player_id,
            sp.name AS nickname,
            t.name AS team_name,
            t.id AS team_id,
            sp.role,
            SUM(CASE WHEN pai.resultado = 1 THEN 1 ELSE 0 END) AS total_partidas_victorias,
            SUM(CASE WHEN pai.resultado = 0 THEN 1 ELSE 0 END) AS total_partidas_derrotas,
            SUM(CASE WHEN pai.resultado = 1 AND pai.kills = pai.max_kills AND pai.count_equal_kills = 1 THEN 1 ELSE 0 END) AS top_kills_unico_victorias,
            SUM(CASE WHEN pai.resultado = 0 AND pai.kills = pai.max_kills AND pai.count_equal_kills = 1 THEN 1 ELSE 0 END) AS top_kills_unico_derrotas,
            SUM(CASE WHEN pai.resultado = 1 AND pai.kills = pai.max_kills AND pai.count_equal_kills > 1 THEN 1 ELSE 0 END) AS top_kills_empate_victorias,
            SUM(CASE WHEN pai.resultado = 0 AND pai.kills = pai.max_kills AND pai.count_equal_kills > 1 THEN 1 ELSE 0 END) AS top_kills_empate_derrotas,
            COALESCE(100.0 * SUM(CASE WHEN pai.resultado = 1 AND pai.kills = pai.max_kills THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN pai.resultado = 1 THEN 1 ELSE 0 END),0), 0) AS pct_top_kills_victorias,
            COALESCE(100.0 * SUM(CASE WHEN pai.resultado = 0 AND pai.kills = pai.max_kills THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN pai.resultado = 0 THEN 1 ELSE 0 END),0), 0) AS pct_top_kills_derrotas
        FROM sports_player sp
        JOIN participant p ON sp.id = p.player_id
        JOIN team t ON t.id = p.team_id
        JOIN top_kills_info pai ON p.game_id = pai.game_id AND p.kills = pai.kills AND pai.resultado = (SELECT gs.resultado FROM game_stats gs WHERE gs.game_id = p.game_id AND gs.team_id = p.team_id)
        WHERE sp.id = %s
        GROUP BY sp.id, sp.name, t.name, t.id, sp.role
        LIMIT 1;
    """, (jugador_id, jugador_id))
    
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
                JOIN MATCHES m ON m.id = g.match_id
                JOIN TOURNAMENT tt on tt.id = m.tournament_id
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
                JOIN MATCHES m ON m.id = g.match_id
                JOIN TOURNAMENT tt on tt.id = m.tournament_id
                WHERE p.player_id = %s AND tt.activo = 1
                ORDER BY g.start_time DESC
            """
            cursor.execute(query, (player_id,))
            
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def obtener_partidas_kills_equipo(team_id):
    """
    Obtiene las estadísticas de kills de un equipo específico en todas sus partidas.
    
    Args:
        team_id (int): ID del equipo a consultar
        
    Returns:
        list: Lista de diccionarios con las estadísticas de cada partida
    """
    connection = None
    cursor = None
    
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT
                v.game_id,
                v.game_num,
                v.start_time AS fecha,
                v.equipo_id,
                v.equipo_nombre,
                v.equipo_img,
                v.team_code,
                v.rival_id,
                v.rival_nombre,
                v.rival_code,
                v.rival_img,
                v.kills_equipo,
                v.kills_rival,
                v.diferencia_kills,
                CASE WHEN v.resultado = 1 THEN TRUE 
                     WHEN v.resultado = 0 THEN FALSE 
                     ELSE NULL END AS resultado
            FROM vista_kills_equipos v
            WHERE v.equipo_id = %s
            ORDER BY v.game_id, v.start_time
        """
        
        cursor.execute(query, (team_id,))
        results = cursor.fetchall()
        
        return results
    
    except mysql.connector.Error as error:
        print(f"Error al obtener partidas de kills del equipo: {error}")
        return []
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def obtener_max_index_leaguepedia(connection, torneo_id):
    """Retorna el máximo index_leaguepedia registrado para el torneo"""
    cursor = connection.cursor()
    try:
        query = """
        SELECT COALESCE(MAX(index_leaguepedia), 0) 
        FROM GAME 
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

def get_ultimas_busquedas():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute('''
        SELECT 
            bej.id,
            bej.datos_formulario,
            bej.fecha,
            bej.team1_id,
            t1.name AS team1_name,
            t1.image AS team1_image,
            bej.team2_id,
            t2.name AS team2_name,
            t2.image AS team2_image,
            CONCAT(
                'Fecha: ', DATE_FORMAT(bej.fecha, '%d/%m/%Y'),
                ' - Teams: ', t1.name, ' vs ', t2.name
            ) as display_text
        FROM BUSQUEDAS_EV_JUGADORES bej
        LEFT JOIN team t1 ON bej.team1_id = t1.id
        LEFT JOIN team t2 ON bej.team2_id = t2.id
        ORDER BY bej.fecha DESC 
        LIMIT 30
    ''')
    
    searches = cursor.fetchall()
    cursor.close()
    return searches

def get_searches_by_id(search_id):
    connection = mysql.connector.connect(**DB_CONFIG)

    cursor = connection.cursor(dictionary=True)
    cursor.execute('''
        SELECT datos_formulario, team1_id, team2_id
        FROM BUSQUEDAS_EV_JUGADORES 
        WHERE id = %s
    ''', (search_id,))
    
    result = cursor.fetchone()
    cursor.close()
    return result