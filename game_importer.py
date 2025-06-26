import calendar
import requests
from datetime import datetime, timezone
from game_importer_leaguepedia import procesar_torneo_leaguepedia
from game_insert import *
from config_local import API_KEY
from mapeo_torneos import MAPEO_TORNEOS


HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://lolesports.com"
}

def fetch_completed_events_by_tournament(tournament_id):
    """Obtiene los eventos completados de un torneo"""
    url = f"https://esports-api.lolesports.com/persisted/gw/getCompletedEvents?hl=en-US&tournamentId={tournament_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)  # 10 segundos de timeout
        response.raise_for_status()
        schedule_data = response.json()
        
        if not isinstance(schedule_data, dict):
            print("❌ schedule_data no es un diccionario:", schedule_data)
            return []
        
        data = schedule_data.get("data")
        if not isinstance(data, dict):
            print("❌ La clave 'data' no es un diccionario:", data)
            return []
        
        schedule = data.get("schedule")
        if not isinstance(schedule, dict):
            print("❌ La clave 'schedule' no es un diccionario:", schedule)
            return []
        
        events = schedule.get("events", [])
        if not isinstance(events, list):
            print("❌ La clave 'events' no es una lista:", events)
            return []
        
    except Exception as e:
        print(f"❌ Error obteniendo eventos del torneo {tournament_id}: {e}")
        return []
    
    eventos_completos = []
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            print(f"❌ Evento #{i} no es un diccionario: {event}")
            continue

        match = event.get("match")
        if not isinstance(match, dict):
            print(f"⚠ Evento #{i} no tiene un match válido: {match}")
            continue

        teams = match.get("teams", [])
        if not isinstance(teams, list) or len(teams) < 2:
            print(f"⚠ Match {match.get('id')} no tiene suficientes equipos, saltando...")
            continue

        print(f"\n🔹 Procesando match {match.get('id')} ...")
        print(f"📅 Fecha y hora: {event.get('startTime')}")
        print(f"🆚 {teams[0].get('name')} vs {teams[1].get('name')}")
        eventos_completos.append(event)
    return eventos_completos

def fetch_game_data(game_id):
    """Obtiene los datos de un juego en vivo"""
    starting_time = get_formatted_starting_time()
    url = f"https://feed.lolesports.com/livestats/v1/window/{game_id}?startingTime={starting_time}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)  # 10 segundos de timeout
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error obteniendo datos del game {game_id}: {e}")
        return None
    
def get_formatted_starting_time():
    # Usar datetime.now() con timezone UTC explícito
    now = datetime.now(timezone.utc) - timedelta(seconds=30)
    
    # Usar calendar.timegm() para tiempo UTC
    rounded_seconds = int(calendar.timegm(now.timetuple()) // 10 * 10)
    
    # Usar fromtimestamp() con timezone UTC explícito
    fecha_utc = datetime.fromtimestamp(rounded_seconds, tz=timezone.utc)
    return fecha_utc.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

def get_team_code_from_participant(participant):
    """Extrae el código del equipo del summonerName del primer participante."""
    name = participant.get('summonerName', '')
    if name:
        return name.split()[0].upper()
    return None

def importar_diferencial(connection, torneos_seleccionados, importar_con_leaguepedia=False):
    cursor = connection.cursor(dictionary=True)
    for torneo_id in torneos_seleccionados:
        if importar_con_leaguepedia and torneo_id in MAPEO_TORNEOS:
            try:
                for nombre_torneo in MAPEO_TORNEOS[torneo_id]:
                    print(f"\n🏆 Procesando torneo {torneo_id} con Leaguepedia: {nombre_torneo}")
                    procesar_torneo_leaguepedia(connection, torneo_id, nombre_torneo)
            except Exception as e:
                print(f"❌ Error al procesar torneo {torneo_id}: {str(e)}")
                continue
        else:
            print(f"\n🏆 Procesando torneo {torneo_id}")
            
            # 1. Obtener eventos completos del torneo (PRIMERO)
            eventos = fetch_completed_events_by_tournament(torneo_id)
            if not eventos:
                print(f"⚠ No se encontraron eventos para el torneo {torneo_id}")
                continue

            # 2. Crear todos los MATCHES del torneo si no existen
            print("🔍 Creando/Actualizando matches...")
            for event in eventos:
                match_data = event.get("match", {})
                if not match_data:
                    continue
                
                # Extraer datos del match
                match_id = int(match_data["id"])
                strategy_type = match_data.get("strategy", {}).get("type")
                strategy_count = match_data.get("strategy", {}).get("count")
                
                # Extraer datos de equipos
                teams = match_data.get("teams", [])
                if len(teams) < 2:
                    continue
                
                team1 = teams[0]
                team2 = teams[1]
                
                # Obtener/crear equipos
                team1_id = get_or_create_team(
                    team1.get("code"), team1.get("name"), team1.get("image"), connection
                )
                team2_id = get_or_create_team(
                    team2.get("code"), team2.get("name"), team2.get("image"), connection
                )
                
                # Obtener/crear match
                get_or_create_match(
                    match_id=match_id,
                    tournament_id=torneo_id,
                    strategy_type=strategy_type,
                    strategy_count=strategy_count,
                    team1_result=team1.get("result", {}).get("gameWins"),
                    team2_result=team2.get("result", {}).get("gameWins"),
                    team1_id=team1_id,
                    team2_id=team2_id,
                    block_name=event.get("blockName"),
                    start_time=parse_iso_time(event.get("startTime")),
                    connection=connection
                )

            # 3. Ahora obtener MATCHES SIN juegos (incluyendo los recién creados)
            query = """
                SELECT M.id 
                FROM MATCHES M
                LEFT JOIN GAME G ON M.id = G.match_id
                WHERE M.tournament_id = %s
                AND G.id IS NULL
            """
            cursor.execute(query, (torneo_id,))
            matches = cursor.fetchall()
            print(f"🔍 {len(matches)} matches sin juegos encontrados")
            
            if not matches:
                print(f"✅ Todos los matches del torneo {torneo_id} ya tienen juegos")
                continue
            
            for match in matches:
                match_id = match['id']
                print(f"\n🔵 Procesando match {match_id}")
                
                # 3. Buscar el evento que corresponde al match
                evento_match = next((
                    e for e in eventos
                    if e.get('match', {}).get('id') == str(match_id)
                ), None)
                
                if not evento_match:
                    print(f"⚠ Match {match_id} no encontrado en la API del torneo")
                    continue
                
                event = evento_match
                
                # Datos generales del evento
                start_time_iso = event.get("startTime")
                try:
                    dt = datetime.strptime(start_time_iso, "%Y-%m-%dT%H:%M:%SZ")
                    start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(f"Error convirtiendo startTime {start_time_iso}: {e}")
                    start_time = None
                
                block_name = event.get("blockName")
                league_name = event.get("league", {}).get("name")
                
                league_id = None
                if league_name:
                    cur_league = connection.cursor()
                    cur_league.execute("SELECT id FROM LEAGUE WHERE name = %s", (league_name,))
                    row_league = cur_league.fetchone()
                    if row_league:
                        league_id = row_league[0]
                    cur_league.close()
                
                match_data = event.get("match", {})
                if not match_data:
                    print(f"⚠ No hay datos de match en el evento para match {match_id}")
                    continue
                
                strategy_type = match_data.get("strategy", {}).get("type")
                strategy_count = match_data.get("strategy", {}).get("count")
                
                teams = match_data.get("teams", [])
                if len(teams) < 2:
                    print(f"⚠ Menos de 2 equipos en match {match_id}, se omite")
                    continue
                
                # Equipo 1
                team1 = teams[0]
                team1_name = team1.get("name")
                team1_code = team1.get("code")
                team1_image = team1.get("image")
                team1_result = team1.get("result", {}).get("gameWins")
                
                # Equipo 2
                team2 = teams[1]
                team2_name = team2.get("name")
                team2_code = team2.get("code")
                team2_image = team2.get("image")
                team2_result = team2.get("result", {}).get("gameWins")
                
                # Obtener o crear equipos
                team1_id = get_or_create_team(team1_code, team1_name, team1_image, connection)
                team2_id = get_or_create_team(team2_code, team2_name, team2_image, connection)
                
                # Obtener o crear match
                match_id = int(match_data["id"])
                match_id = get_or_create_match(
                    match_id, torneo_id, strategy_type, strategy_count,
                    team1_result, team2_result, team1_id, team2_id,
                    block_name, start_time, connection
                )
                
                print(f"Match {match_id} procesado para torneo {torneo_id}.")
                
                # 4. Procesar juegos del match
                games = event.get("games", [])
                print(f"🎮 {len(games)} juegos encontrados en el match")
                    
                for game_idx, game in enumerate(games):
                        game_num = game_idx + 1
                        game_id = game.get("id")
                        print(f"\n    🕹️ Game {game_num} (ID: {game_id})")
                        
                        game_stats = fetch_game_data(game_id)
                        if not game_stats:
                            print(f"    ⚠ No se pudieron obtener datos para el game_id: {game_id}")
                            continue
                        
                        frames = game_stats.get("frames", [])
                        if not frames:
                            print(f"    ⚠ Sin frames disponibles para el game_id: {game_id}")
                            continue
                            
                        last_frame = frames[-1]
                        print(f"    ⏱️ Último frame: {last_frame.get('rfc460Timestamp')}")
                        
                        # Procesar equipos azul y rojo
                        blue_team_metadata = game_stats.get("gameMetadata", {}).get("blueTeamMetadata", {})
                        blue_team_stats = last_frame.get("blueTeam")
                        blue_participants = blue_team_metadata.get("participantMetadata", []) if blue_team_metadata else []
                        blue_team_id = None
                        ganador = determine_winner( last_frame)
                        if blue_participants:
                            blue_team_code = get_team_code_from_participant(blue_participants[0])
                            blue_team_id = get_team_id_by_code(cursor, blue_team_code)
                            print(f"    🔷 ID interno equipo azul: {blue_team_id}")
                        else:
                            print("    ⚠ No se encontraron participantes azules")

                        
                        red_team_metadata = game_stats.get("gameMetadata", {}).get("redTeamMetadata", {})
                        red_team_stats = last_frame.get("redTeam")
                        red_participants = red_team_metadata.get("participantMetadata", []) if red_team_metadata else []
                        patch = game_stats.get("patchVersion")
                        red_team_id = None
                        if red_participants:
                            red_team_code = get_team_code_from_participant(red_participants[0])
                            red_team_id = get_team_id_by_code(cursor, red_team_code)
                            print(f"    🔴 ID interno equipo rojo: {red_team_id}")
                        else:
                            print("    ⚠ No se encontraron participantes rojos")
                    
                        # Insertar el juego
                        try:
                            insert_game(cursor, game_id, match_id, last_frame.get("rfc460Timestamp"), game_num, None, patch, None, None)
                        except Exception as e:
                            print(f"    ❌ Error insertando juego: {str(e)}")
                            continue
                        # Insertar stats del equipo azul
                        if blue_team_stats and blue_team_id:
                            try:
                                insert_game_stats(cursor, game_id, blue_team_id, "blue", blue_team_stats, ganador)
                                print(f"    📊 Estadísticas azules insertadas: {len(blue_team_stats['dragons'])} dragones")
                            except Exception as e:
                                print(f"    ❌ Error insertando stats azules: {str(e)}")
                        elif not blue_team_stats:
                            print(f"    ⚠ No hay estadísticas para el equipo azul en el juego {game_id}")
                        elif not blue_team_id:
                            print(f"    ⚠ No se encontró team_id para el equipo azul")
                        # Insertar stats del equipo rojo
                        if red_team_stats and red_team_id:
                            try:
                                insert_game_stats(cursor, game_id, red_team_id, "red", red_team_stats, ganador)
                                print(f"    📊 Estadísticas rojas insertadas: {len(red_team_stats['dragons'])} dragones")
                            except Exception as e:
                                print(f"    ❌ Error insertando stats rojas: {str(e)}")
                        elif not red_team_stats:
                            print(f"    ⚠ No hay estadísticas para el equipo rojo en el juego {game_id}")
                        elif not red_team_id:
                            print(f"    ⚠ No se encontró team_id para el equipo rojo")
                        # Procesar participantes
                        print("\n    👤 Procesando participantes...")
                        participants_data = []

                        # Equipo azul
                        for p_idx, metadata_participant in enumerate(blue_participants):
                            participant_id = metadata_participant.get("participantId")
                            champion_code = metadata_participant.get("championId")
                            champion_id = get_champion_id(cursor, champion_code)
                            frame_participants = blue_team_stats.get("participants", []) if blue_team_stats else []
                            frame_stats = next(
                                (p for p in frame_participants if p.get("participantId") == participant_id),
                                None
                            )
                            if not frame_stats:
                                print(f"      ❌ No se encontraron stats para participantId {participant_id}")
                                continue
                            merged_data = {
                                **metadata_participant,
                                **frame_stats,
                                "teamId": blue_team_id,
                                "championId": champion_id
                            }
                            participants_data.append(merged_data)

                        # Equipo rojo
                        for p_idx, metadata_participant in enumerate(red_participants):
                            participant_id = metadata_participant.get("participantId")
                            champion_code = metadata_participant.get("championId")
                            champion_id = get_champion_id(cursor, champion_code)
                            frame_participants = red_team_stats.get("participants", []) if red_team_stats else []
                            frame_stats = next(
                                (p for p in frame_participants if p.get("participantId") == participant_id),
                                None
                            )
                            if not frame_stats:
                                print(f"      ❌ No se encontraron stats para participantId {participant_id}")
                                continue
                            merged_data = {
                                **metadata_participant,
                                **frame_stats,
                                "teamId": red_team_id,
                                "championId": champion_id
                            }
                            participants_data.append(merged_data)

                        # Insertar participantes
                        print(f"\n    📥 Insertando {len(participants_data)} participantes...")
                        for p_idx, participant in enumerate(participants_data):
                            try:
                                player_name = participant.get("summonerName")
                                team_id = participant.get("teamId")
                                champion_id = participant.get("championId")
                                participant_id = participant.get("participantId")
                                if not all([player_name, team_id, champion_id]):
                                    print(f"      ⚠ Datos incompletos en participante {p_idx + 1}")
                                    continue
                                print(f"      👤 {player_name} (Team: {team_id}, Champion: {champion_id})")
                                player_id = get_or_create_player(cursor, player_name, participant_id, team_id)
                                insert_participant(cursor, game_id, player_id, team_id, champion_id, participant)
                            except Exception as e:
                                print(f"      ❌ Error insertando participante {p_idx + 1}: {str(e)}")
                                continue

                        connection.commit()
                        print("    ✅ Commit realizado correctamente")
                ajustar_games_match(connection, match)   
        
    cursor.close()

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
    
