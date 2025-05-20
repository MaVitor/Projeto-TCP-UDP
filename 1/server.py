import socket
import threading
import time
import random
import json

# Configurações do servidor
TCP_HOST = '127.0.0.1'
TCP_PORT = 5000
UDP_PORT = 5001

# Configurações do jogo
MIN_MULTIPLIER = 1.0
MAX_MULTIPLIER = 10.0
CRASH_PROBABILITY = 0.05  # 5% de chance de crash a cada tick
TICK_RATE = 0.1  # segundos entre cada atualização

# Estado do jogo
game_state = {
    "status": "waiting",  # waiting, running, crashed
    "multiplier": 1.0,
    "players": {},  # {client_addr: {"bet": amount, "cash_out": multiplier}}
    "history": []
}

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_socket.bind((TCP_HOST, TCP_PORT))
tcp_socket.listen(5)

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.bind((TCP_HOST, UDP_PORT))

print(f"Servidor iniciado - TCP: {TCP_HOST}:{TCP_PORT}, UDP: {TCP_HOST}:{UDP_PORT}")

# Função para lidar com conexões TCP (apostas e comandos)
def handle_tcp_client(client_socket, client_addr):
    print(f"Nova conexão TCP de {client_addr}")
    
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
                
            message = json.loads(data.decode('utf-8'))
            command = message.get("command")
            
            if command == "bet":
                if game_state["status"] == "waiting":
                    amount = message.get("amount", 0)
                    if amount > 0:
                        game_state["players"][client_addr] = {
                            "bet": amount,
                            "cash_out": None
                        }
                        response = {"status": "bet_accepted", "amount": amount}
                else:
                    response = {"status": "error", "message": "Game already in progress"}
                    
            elif command == "cash_out":
                if game_state["status"] == "running":
                    if client_addr in game_state["players"] and game_state["players"][client_addr]["cash_out"] is None:
                        game_state["players"][client_addr]["cash_out"] = game_state["multiplier"]
                        winnings = game_state["players"][client_addr]["bet"] * game_state["multiplier"]
                        response = {"status": "cash_out_success", "multiplier": game_state["multiplier"], "winnings": winnings}
                    else:
                        response = {"status": "error", "message": "No active bet or already cashed out"}
                else:
                    response = {"status": "error", "message": "Game not in progress"}
            
            elif command == "status":
                response = {
                    "status": "game_status",
                    "game_status": game_state["status"],
                    "multiplier": game_state["multiplier"],
                    "history": game_state["history"][-10:]
                }
            
            else:
                response = {"status": "error", "message": "Unknown command"}
                
            client_socket.send(json.dumps(response).encode('utf-8'))
            
    except Exception as e:
        print(f"Erro na conexão TCP com {client_addr}: {e}")
    finally:
        client_socket.close()
        print(f"Conexão TCP com {client_addr} encerrada")

# Função para enviar atualizações do jogo via UDP
def broadcast_game_updates():
    while True:
        update = {
            "status": game_state["status"],
            "multiplier": game_state["multiplier"]
        }
        message = json.dumps(update).encode('utf-8')
        
        # Enviar para todos os jogadores conectados
        for addr in game_state["players"].keys():
            try:
                udp_socket.sendto(message, addr)
            except:
                pass
                
        time.sleep(TICK_RATE)

# Função principal do jogo
def game_loop():
    global game_state
    
    while True:
        # Fase de espera para apostas
        game_state["status"] = "waiting"
        game_state["multiplier"] = 1.0
        print("Aguardando apostas (10 segundos)...")
        time.sleep(10)  # Tempo para apostas
        
        if not game_state["players"]:
            continue  # Se não houver apostas, reinicia o ciclo
            
        # Inicia o jogo
        game_state["status"] = "running"
        print("Jogo iniciado!")
        
        # Loop do jogo - aumenta o multiplicador até crashar
        crashed = False
        while not crashed:
            # Aumenta o multiplicador
            game_state["multiplier"] += 0.01
            
            # Verifica se deve crashar
            if (random.random() < CRASH_PROBABILITY or 
                game_state["multiplier"] >= MAX_MULTIPLIER):
                crashed = True
                break
                
            time.sleep(TICK_RATE)
        
        # Jogo terminou (crash)
        game_state["status"] = "crashed"
        print(f"CRASH em {game_state['multiplier']:.2f}x")
        
        # Registra o resultado no histórico
        game_state["history"].append(game_state["multiplier"])
        
        # Calcula resultados para cada jogador
        for addr, player_data in game_state["players"].items():
            if player_data["cash_out"] is not None:
                winnings = player_data["bet"] * player_data["cash_out"]
                print(f"Jogador {addr} ganhou {winnings:.2f} (cash out em {player_data['cash_out']:.2f}x)")
            else:
                print(f"Jogador {addr} perdeu {player_data['bet']:.2f}")
        
        # Limpa os jogadores para a próxima rodada
        game_state["players"] = {}
        
        # Pequena pausa antes da próxima rodada
        time.sleep(3)

# Inicia as threads
threading.Thread(target=game_loop, daemon=True).start()
threading.Thread(target=broadcast_game_updates, daemon=True).start()

# Loop principal para aceitar conexões TCP
try:
    while True:
        client_socket, client_addr = tcp_socket.accept()
        threading.Thread(target=handle_tcp_client, args=(client_socket, client_addr), daemon=True).start()
except KeyboardInterrupt:
    print("Servidor encerrado.")
finally:
    tcp_socket.close()
    udp_socket.close()