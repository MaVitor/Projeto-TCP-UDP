import socket
import threading
import time
import random
import json
import sys
import os
import pickle

# Configurações do servidor - Alterado para aceitar conexões de qualquer IP
TCP_HOST = '0.0.0.0'  # Aceita conexões de qualquer endereço
TCP_PORT = 5000
UDP_PORT = 5001

# Configurações do jogo
MIN_MULTIPLIER = 1.0
MAX_MULTIPLIER = 10.0
CRASH_PROBABILITY = 0.03  # 3% de chance de crash a cada tick
TICK_RATE = 0.1  # segundos entre cada atualização

# Arquivo para salvar os dados dos jogadores
PLAYERS_DATA_FILE = "players_data.pkl"

# Estado do jogo
game_state = {
    "status": "waiting",  # waiting, running, crashed
    "multiplier": 1.0,
    "players": {},  # {client_addr: {"bet": amount, "cash_out": multiplier, "name": player_name}}
    "history": []
}

# Ranking de jogadores
player_balances = {}  # {player_name: balance}
player_ips = {}  # {player_name: ip_address} - Para verificar se o jogador já existe

# Carregar dados dos jogadores se o arquivo existir
def load_players_data():
    global player_balances, player_ips
    try:
        if os.path.exists(PLAYERS_DATA_FILE):
            with open(PLAYERS_DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                player_balances = data.get('balances', {})
                player_ips = data.get('ips', {})
                print(f"Dados de {len(player_balances)} jogadores carregados.")
    except Exception as e:
        print(f"Erro ao carregar dados dos jogadores: {e}")
        player_balances = {}
        player_ips = {}

# Salvar dados dos jogadores
def save_players_data():
    try:
        data = {
            'balances': player_balances,
            'ips': player_ips
        }
        with open(PLAYERS_DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        print(f"Dados de {len(player_balances)} jogadores salvos.")
    except Exception as e:
        print(f"Erro ao salvar dados dos jogadores: {e}")

# Carregar dados dos jogadores ao iniciar
load_players_data()

# Flag para controlar o servidor
server_running = True

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_socket.bind((TCP_HOST, TCP_PORT))
tcp_socket.listen(5)

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind((TCP_HOST, UDP_PORT))

# Obter o endereço IP local para exibir
def get_local_ip():
    try:
        # Cria um socket temporário para descobrir o IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

local_ip = get_local_ip()
print(f"Servidor iniciado - IP: {local_ip}, TCP: {TCP_PORT}, UDP: {UDP_PORT}")
print(f"Compartilhe este IP com outros jogadores na mesma rede: {local_ip}")
print("\nComandos disponíveis:")
print("  stop - Para o servidor")
print("  status - Mostra o status atual do jogo")
print("  players - Lista os jogadores conectados")
print("  history - Mostra o histórico de resultados")
print("  save - Salva os dados dos jogadores manualmente")
print("  help - Mostra esta ajuda")

# Dicionário para mapear endereços TCP para endereços UDP e nomes de jogadores
udp_clients = {}  # {client_addr: {"udp_addr": (ip, port), "name": player_name}}

# Função para obter o ranking atual
def get_leaderboard():
    # Ordenar por saldo
    sorted_players = sorted(player_balances.items(), key=lambda x: x[1], reverse=True)
    
    # Converter para o formato esperado pelo cliente
    leaderboard = [{"name": name, "balance": balance} for name, balance in sorted_players]
    
    # Limitar a 10 jogadores
    return leaderboard[:10]

# Função para verificar se um nome de jogador já existe
def check_player_exists(player_name, client_ip):
    # Verificar se o nome já existe
    if player_name in player_balances:
        # Verificar se o IP corresponde ao registrado
        if player_name in player_ips and player_ips[player_name] != client_ip:
            return {"status": "error", "message": "Este nome já está em uso por outro jogador."}
        # Se o IP corresponder, o jogador está apenas reconectando
        return {"status": "ok", "balance": player_balances[player_name]}
    
    # Verificar se o IP já está associado a outro nome
    for name, ip in player_ips.items():
        if ip == client_ip and name != player_name:
            return {"status": "error", "message": f"Você já está registrado como '{name}'. Não é permitido criar múltiplas contas."}
    
    # Novo jogador
    player_balances[player_name] = 1000  # Saldo inicial
    player_ips[player_name] = client_ip
    save_players_data()  # Salvar dados após registrar novo jogador
    return {"status": "ok", "balance": 1000, "message": "Novo jogador registrado com sucesso!"}

# Função para lidar com conexões TCP (apostas e comandos)
def handle_tcp_client(client_socket, client_addr):
    global player_balances, server_running
    
    print(f"Nova conexão TCP de {client_addr}")
    player_name = None
    client_ip = client_addr[0]
    
    try:
        while server_running:
            data = client_socket.recv(1024)
            if not data:
                break
                
            message = json.loads(data.decode('utf-8'))
            command = message.get("command")
            
            # Obter o nome do jogador se disponível
            if "player_name" in message:
                player_name = message["player_name"]
            
            if command == "check_name":
                player_name = message.get("player_name", "")
                if player_name:
                    result = check_player_exists(player_name, client_ip)
                    response = result
                else:
                    response = {"status": "error", "message": "Nome de jogador inválido"}
            
            elif command == "bet":
                if game_state["status"] == "waiting":
                    amount = message.get("amount", 0)
                    
                    # Verificar se é uma aposta de "all-in"
                    if amount == "all":
                        if player_name in player_balances:
                            amount = player_balances[player_name]
                        else:
                            amount = 0
                    
                    if amount > 0:
                        game_state["players"][client_addr] = {
                            "bet": amount,
                            "cash_out": None,
                            "name": player_name
                        }
                        response = {"status": "bet_accepted", "amount": amount}
                        print(f"Aposta de {amount} aceita de {player_name} ({client_addr})")
                        
                        # Atualizar saldo do jogador
                        if player_name:
                            player_balances[player_name] -= amount
                            save_players_data()  # Salvar após cada aposta
                    else:
                        response = {"status": "error", "message": "Invalid bet amount"}
                else:
                    response = {"status": "error", "message": "Game already in progress"}
                    
            elif command == "cash_out":
                if game_state["status"] == "running":
                    if client_addr in game_state["players"] and game_state["players"][client_addr]["cash_out"] is None:
                        game_state["players"][client_addr]["cash_out"] = game_state["multiplier"]
                        winnings = game_state["players"][client_addr]["bet"] * game_state["multiplier"]
                        response = {"status": "cash_out_success", "multiplier": game_state["multiplier"], "winnings": winnings}
                        print(f"Cash out de {player_name} ({client_addr}) em {game_state['multiplier']:.2f}x, ganhou {winnings:.2f}")
                        
                        # Atualizar saldo do jogador
                        if player_name:
                            player_balances[player_name] += winnings
                            save_players_data()  # Salvar após cada cash out
                    else:
                        response = {"status": "error", "message": "No active bet or already cashed out"}
                        print(f"Erro no cash out de {player_name} ({client_addr}): sem aposta ativa ou já fez cash out")
                else:
                    response = {"status": "error", "message": "Game not in progress"}
                    print(f"Erro no cash out de {player_name} ({client_addr}): jogo não está em andamento")
            
            elif command == "status":
                response = {
                    "status": "game_status",
                    "game_status": game_state["status"],
                    "multiplier": game_state["multiplier"],
                    "history": game_state["history"][-10:],
                    "leaderboard": get_leaderboard()
                }
            
            elif command == "register_udp":
                # Registrar o endereço UDP do cliente
                udp_addr = message.get("udp_addr")
                if udp_addr:
                    # Importante: usar o IP do cliente, não o que ele enviou
                    client_ip = client_addr[0]
                    udp_port = udp_addr[1]
                    udp_clients[client_addr] = {
                        "udp_addr": (client_ip, udp_port),
                        "name": player_name
                    }
                    print(f"Cliente {player_name} ({client_addr}) registrou UDP em {client_ip}:{udp_port}")
                    response = {"status": "udp_registered"}
                else:
                    response = {"status": "error", "message": "Invalid UDP address"}
            
            else:
                response = {"status": "error", "message": "Unknown command"}
                
            client_socket.send(json.dumps(response).encode('utf-8'))
            
    except Exception as e:
        print(f"Erro na conexão TCP com {client_addr}: {e}")
    finally:
        client_socket.close()
        print(f"Conexão TCP com {client_addr} encerrada")
        # Remover o jogador se desconectar
        if client_addr in game_state["players"]:
            del game_state["players"][client_addr]
        if client_addr in udp_clients:
            del udp_clients[client_addr]

# Função para enviar atualizações do jogo via UDP
def broadcast_game_updates():
    global server_running
    
    while server_running:
        update = {
            "status": game_state["status"],
            "multiplier": game_state["multiplier"],
            "leaderboard": get_leaderboard()
        }
        message = json.dumps(update).encode('utf-8')
        
        # Enviar para todos os jogadores conectados via UDP
        for client_addr, client_info in udp_clients.items():
            try:
                udp_socket.sendto(message, client_info["udp_addr"])
            except Exception as e:
                print(f"Erro ao enviar UDP para {client_info['udp_addr']}: {e}")
                
        time.sleep(TICK_RATE)

# Função principal do jogo
def game_loop():
    global game_state, server_running
    
    while server_running:
        # Fase de espera para apostas
        game_state["status"] = "waiting"
        game_state["multiplier"] = 1.0
        print("Aguardando apostas (10 segundos)...")
        
        # Esperar por apostas, mas verificar a flag server_running a cada segundo
        for _ in range(10):
            if not server_running:
                break
            time.sleep(1)
            
        if not server_running:
            break
            
        if not game_state["players"]:
            continue  # Se não houver apostas, reinicia o ciclo
            
        # Inicia o jogo
        game_state["status"] = "running"
        print("Jogo iniciado!")
        
        # Loop do jogo - aumenta o multiplicador até crashar
        crashed = False
        while not crashed and server_running:
            # Aumenta o multiplicador
            game_state["multiplier"] += 0.01
            
            # Verifica se deve crashar
            if (random.random() < CRASH_PROBABILITY or 
                game_state["multiplier"] >= MAX_MULTIPLIER):
                crashed = True
                break
                
            time.sleep(TICK_RATE)
        
        if not server_running:
            break
            
        # Jogo terminou (crash)
        game_state["status"] = "crashed"
        print(f"CRASH em {game_state['multiplier']:.2f}x")
        
        # Registra o resultado no histórico
        game_state["history"].append(game_state["multiplier"])
        
        # Calcula resultados para cada jogador
        for addr, player_data in game_state["players"].items():
            player_name = player_data.get("name", "Desconhecido")
            
            if player_data["cash_out"] is not None:
                winnings = player_data["bet"] * player_data["cash_out"]
                print(f"Jogador {player_name} ({addr}) ganhou {winnings:.2f} (cash out em {player_data['cash_out']:.2f}x)")
            else:
                print(f"Jogador {player_name} ({addr}) perdeu {player_data['bet']:.2f}")
        
        # Limpa os jogadores para a próxima rodada
        game_state["players"] = {}
        
        # Pequena pausa antes da próxima rodada
        for _ in range(3):
            if not server_running:
                break
            time.sleep(1)

# Função para processar comandos do terminal
def process_terminal_commands():
    global server_running
    
    while server_running:
        try:
            command = input().strip().lower()
            
            if command == "stop":
                print("Parando o servidor...")
                server_running = False
                save_players_data()  # Salvar dados antes de encerrar
                break
                
            elif command == "status":
                print(f"Status do jogo: {game_state['status']}")
                print(f"Multiplicador atual: {game_state['multiplier']:.2f}x")
                print(f"Jogadores com apostas ativas: {len(game_state['players'])}")
                
            elif command == "players":
                print("Jogadores registrados:")
                for name, balance in player_balances.items():
                    ip = player_ips.get(name, "Desconhecido")
                    print(f"  {name} - Saldo: {balance:.2f} - IP: {ip}")
                    
            elif command == "history":
                print("Histórico de resultados:")
                for i, result in enumerate(reversed(game_state["history"][-10:])):
                    print(f"  {i+1}. {result:.2f}x")
            
            elif command == "save":
                save_players_data()
                print("Dados dos jogadores salvos manualmente.")
                    
            elif command == "help":
                print("\nComandos disponíveis:")
                print("  stop - Para o servidor")
                print("  status - Mostra o status atual do jogo")
                print("  players - Lista os jogadores conectados")
                print("  history - Mostra o histórico de resultados")
                print("  save - Salva os dados dos jogadores manualmente")
                print("  help - Mostra esta ajuda")
                
            else:
                print(f"Comando desconhecido: {command}")
                print("Digite 'help' para ver os comandos disponíveis")
                
        except Exception as e:
            print(f"Erro ao processar comando: {e}")

# Inicia as threads
game_thread = threading.Thread(target=game_loop, daemon=True)
game_thread.start()

broadcast_thread = threading.Thread(target=broadcast_game_updates, daemon=True)
broadcast_thread.start()

command_thread = threading.Thread(target=process_terminal_commands, daemon=True)
command_thread.start()

# Loop principal para aceitar conexões TCP
try:
    # Configurar timeout para o socket TCP para poder verificar a flag server_running
    tcp_socket.settimeout(1.0)
    
    while server_running:
        try:
            client_socket, client_addr = tcp_socket.accept()
            threading.Thread(target=handle_tcp_client, args=(client_socket, client_addr), daemon=True).start()
        except socket.timeout:
            # Timeout é normal, continua o loop
            continue
        except Exception as e:
            print(f"Erro ao aceitar conexão: {e}")
            time.sleep(1)
            
except KeyboardInterrupt:
    print("Servidor encerrado pelo usuário (Ctrl+C).")
finally:
    server_running = False
    print("Salvando dados dos jogadores...")
    save_players_data()
    print("Fechando conexões...")
    tcp_socket.close()
    udp_socket.close()
    print("Servidor encerrado.")
    sys.exit(0)