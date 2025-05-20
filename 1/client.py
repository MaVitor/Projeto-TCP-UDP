import socket
import threading
import json
import time
import sys

# Configurações do cliente
SERVER_HOST = '127.0.0.1'
TCP_PORT = 5000
UDP_PORT = 5001

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Conectar ao servidor
try:
    tcp_socket.connect((SERVER_HOST, TCP_PORT))
    print(f"Conectado ao servidor {SERVER_HOST}:{TCP_PORT}")
    
    # Configurar socket UDP para receber atualizações
    udp_socket.bind(('0.0.0.0', 0))  # Porta aleatória
    client_address = tcp_socket.getsockname()
except Exception as e:
    print(f"Erro ao conectar: {e}")
    sys.exit(1)

# Variáveis de estado do cliente
current_multiplier = 1.0
game_status = "waiting"
has_active_bet = False
bet_amount = 0

# Função para receber atualizações UDP
def receive_udp_updates():
    global current_multiplier, game_status
    
    while True:
        try:
            data, _ = udp_socket.recvfrom(1024)
            update = json.loads(data.decode('utf-8'))
            
            current_multiplier = update["multiplier"]
            game_status = update["status"]
            
            # Exibe o multiplicador atual
            if game_status == "running":
                print(f"\rMultiplicador atual: {current_multiplier:.2f}x", end="")
            elif game_status == "crashed" and has_active_bet:
                print(f"\nCRASH em {current_multiplier:.2f}x!")
                
        except Exception as e:
            print(f"\nErro ao receber atualização UDP: {e}")
            break

# Função para enviar comandos TCP
def send_tcp_command(command, **kwargs):
    message = {"command": command, **kwargs}
    try:
        tcp_socket.send(json.dumps(message).encode('utf-8'))
        response = tcp_socket.recv(1024)
        return json.loads(response.decode('utf-8'))
    except Exception as e:
        print(f"Erro ao enviar comando: {e}")
        return None

# Função para exibir o menu
def show_menu():
    print("\n===== JOGO CRASH =====")
    print("1. Fazer aposta")
    print("2. Cash out")
    print("3. Ver status do jogo")
    print("4. Sair")
    return input("Escolha uma opção: ")

# Inicia a thread para receber atualizações UDP
threading.Thread(target=receive_udp_updates, daemon=True).start()

# Loop principal do cliente
try:
    while True:
        choice = show_menu()
        
        if choice == "1":
            if game_status == "waiting" and not has_active_bet:
                try:
                    amount = float(input("Valor da aposta: "))
                    response = send_tcp_command("bet", amount=amount)
                    
                    if response and response["status"] == "bet_accepted":
                        print(f"Aposta de {amount} aceita!")
                        has_active_bet = True
                        bet_amount = amount
                    else:
                        print(f"Erro: {response.get('message', 'Aposta não aceita')}")
                except ValueError:
                    print("Por favor, insira um valor numérico válido.")
            else:
                print("Não é possível apostar agora. Aguarde a próxima rodada ou você já tem uma aposta ativa.")
                
        elif choice == "2":
            if game_status == "running" and has_active_bet:
                response = send_tcp_command("cash_out")
                
                if response and response["status"] == "cash_out_success":
                    print(f"Cash out realizado com sucesso em {response['multiplier']:.2f}x!")
                    print(f"Você ganhou {response['winnings']:.2f}!")
                    has_active_bet = False
                else:
                    print(f"Erro: {response.get('message', 'Cash out falhou')}")
            else:
                print("Não é possível fazer cash out agora.")
                
        elif choice == "3":
            response = send_tcp_command("status")
            
            if response and response["status"] == "game_status":
                print(f"\nStatus do jogo: {response['game_status']}")
                print(f"Multiplicador atual: {response['multiplier']:.2f}x")
                
                if response["history"]:
                    print("Histórico recente:")
                    for mult in response["history"]:
                        print(f"  {mult:.2f}x")
            else:
                print("Erro ao obter status do jogo.")
                
        elif choice == "4":
            print("Saindo do jogo...")
            break
            
        else:
            print("Opção inválida. Tente novamente.")
            
        # Pequena pausa para não sobrecarregar o terminal
        time.sleep(0.5)
        
except KeyboardInterrupt:
    print("\nPrograma encerrado pelo usuário.")
finally:
    tcp_socket.close()
    udp_socket.close()