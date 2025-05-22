import socket
import threading
import json
import time
import sys

# Configurações do cliente
SERVER_HOST = '192.168.56.1'
TCP_PORT = 5000
UDP_PORT = 5001

# Inicializar sockets
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

player_name = "JogadorAnônimo"

# Conectar ao servidor
try:
    print(f"Tentando conectar ao servidor {SERVER_HOST}:{TCP_PORT}...")
    tcp_socket.connect((SERVER_HOST, TCP_PORT))
    print(f"Conectado ao servidor {SERVER_HOST}:{TCP_PORT}")

    udp_socket.bind(('0.0.0.0', UDP_PORT))
    print(f"Escutando por atualizações UDP na porta {UDP_PORT}")

    while True:
        name_input = input("Digite seu nome para o jogo: ").strip()
        if name_input:
            player_name = name_input
            name_set_message = {"command": "set_name", "name": player_name}
            tcp_socket.send(json.dumps(name_set_message).encode('utf-8'))
            response_name_raw = tcp_socket.recv(1024)
            response_name = json.loads(response_name_raw.decode('utf-8'))
            if response_name.get("status") == "name_set_ok":
                print(f"Nome '{player_name}' registrado no servidor.")
            else:
                print(f"Servidor respondeu sobre o nome: {response_name.get('message', 'Status desconhecido')}")
            break
        else:
            print("Nome não pode ser vazio. Tente novamente.")

except Exception as e:
    print(f"Erro ao conectar ou configurar nome: {e}")
    sys.exit(1)

# Variáveis de estado do cliente
current_multiplier = 1.0
game_status = "waiting"
has_active_bet = False
bet_amount = 0
client_balance = 0.0
last_known_server_game_status = "waiting"

# Função para receber atualizações UDP
def receive_udp_updates():
    global current_multiplier, game_status, has_active_bet, bet_amount, last_known_server_game_status

    while True:
        try:
            data, _ = udp_socket.recvfrom(1024)
            update = json.loads(data.decode('utf-8'))

            current_multiplier = update.get("multiplier", current_multiplier)
            new_server_status = update.get("status", game_status)

            if new_server_status == "crashed" and last_known_server_game_status != "crashed":
                display_name_info = f" ({player_name})" if player_name != "JogadorAnônimo" else ""
                if has_active_bet:
                    sys.stdout.write(f"\rCRASH em {current_multiplier:.2f}x! Você{display_name_info} não sacou a tempo.                                \n")
                else:
                    sys.stdout.write(f"\rCRASH em {current_multiplier:.2f}x!                                                           \n")
                has_active_bet = False
                bet_amount = 0
            elif new_server_status == "waiting" and last_known_server_game_status != "waiting":
                if last_known_server_game_status != "waiting":
                    sys.stdout.write("\rNova rodada começando. Faça sua aposta!                                                    \n")
                has_active_bet = False
                bet_amount = 0

            game_status = new_server_status
            last_known_server_game_status = new_server_status

            if game_status == "running":
                sys.stdout.write(f"\rMultiplicador atual: {current_multiplier:.2f}x  ")
                sys.stdout.flush()
            
        except json.JSONDecodeError:
            pass
        except OSError:
             break 
        except Exception:
            pass

# Função para enviar comandos TCP e atualizar saldo
def send_tcp_command(command, **kwargs):
    global client_balance
    message = {"command": command, **kwargs}
    try:
        tcp_socket.send(json.dumps(message).encode('utf-8'))
        response_data = tcp_socket.recv(1024)
        if not response_data:
            print("\nServidor não enviou resposta (conexão fechada?).")
            return {"status": "error", "message": "Sem resposta do servidor"}
        response = json.loads(response_data.decode('utf-8'))

        if "balance" in response: # Atualiza saldo se presente na resposta do servidor
            client_balance = float(response["balance"])
        if response.get("status") == "error" and "message" in response and "Saldo insuficiente" in response["message"]:
             # Caso especial para saldo insuficiente, o saldo já está atualizado
             pass # Não precisa fazer nada extra com o saldo aqui
        elif "balance" in response and response.get("status") != "error": # Outras respostas OK com saldo
             client_balance = float(response["balance"])

        return response
    except (ConnectionResetError, BrokenPipeError): # Trata ambas as exceções de conexão
        print("\nErro: Conexão com o servidor foi perdida.")
        # Tenta fechar o programa de forma mais controlada
        # Pode-se adicionar uma flag para parar o loop principal
        global running_client
        running_client = False # Sinaliza para o loop principal parar
        return {"status": "error", "message": "Conexão perdida"}
    except json.JSONDecodeError:
        print("\nErro ao decodificar resposta do servidor.")
        return {"status": "error", "message": "Resposta inválida do servidor"}
    except Exception as e:
        print(f"Erro ao enviar/receber comando TCP: {e}")
        return None

# Função para exibir o menu
def show_menu():
    sys.stdout.write("\r" + " " * 80 + "\r") 
    sys.stdout.flush()
    print(f"\n===== JOGO CRASH (Jogador: {player_name}, Saldo: R${client_balance:.2f}) =====")
    print("1. Fazer aposta")
    print("2. Cash out")
    print("3. Ver status do jogo e Saldo")
    print("4. Ver Ranking dos Melhores Jogadores") # NOVA OPÇÃO
    print("5. Sair") # Sair agora é 5
    return input("Escolha uma opção: ")

# Solicita o status inicial para obter o saldo
print("Obtendo saldo inicial do servidor...")
initial_status_response = send_tcp_command("status")
if initial_status_response and "balance" in initial_status_response:
    client_balance = float(initial_status_response["balance"])
    # O nome pode vir do status também se o servidor o enviar
    if "player_name" in initial_status_response and initial_status_response["player_name"] != player_name and initial_status_response["player_name"] != f"{DEFAULT_PLAYER_NAME}_{SERVER_HOST.split('.')[-1]}": # Evita sobrescrever nome recém-digitado com default
        player_name = initial_status_response["player_name"]
        print(f"Nome '{player_name}' e saldo inicial R${client_balance:.2f} carregados.")
    else:
        print(f"Saldo inicial R${client_balance:.2f} carregado.")

else:
    print("Não foi possível obter o saldo inicial do servidor.")


# Inicia a thread para receber atualizações UDP
udp_thread = threading.Thread(target=receive_udp_updates, daemon=True)
udp_thread.start()

running_client = True # Flag para controlar o loop principal em caso de erro de conexão

# Loop principal do cliente
try:
    while running_client: # Modificado para usar a flag
        if game_status != "running":
            sys.stdout.write("\r" + " " * 70 + "\r")
        
        choice = show_menu()

        if not running_client: break # Verifica a flag após o input

        if choice == "1":
            if game_status == "waiting":
                if has_active_bet:
                     print("Você já tem uma aposta ativa para esta rodada.")
                     continue
                try:
                    amount_str = input(f"Seu saldo atual: R${client_balance:.2f}. Valor da aposta: ")
                    amount = float(amount_str)
                    if amount <= 0:
                        print("O valor da aposta deve ser positivo.")
                        continue

                    response = send_tcp_command("bet", amount=amount)
                    if not running_client: break # Verifica após o comando

                    if response and response.get("status") == "bet_accepted":
                        print(f"Aposta de R${response.get('amount', amount):.2f} aceita! Novo saldo: R${client_balance:.2f}")
                        has_active_bet = True
                        bet_amount = amount
                    else:
                        print(f"Erro ao apostar: {response.get('message', 'Aposta não aceita') if response else 'Sem resposta'}")
                except ValueError:
                    print("Por favor, insira um valor numérico válido.")
                except Exception as e:
                    print(f"Ocorreu um erro: {e}")
            else:
                print("Não é possível apostar agora (jogo não está em 'waiting' ou você já apostou).")

        elif choice == "2":
            if game_status == "running" and has_active_bet:
                response = send_tcp_command("cash_out")
                if not running_client: break

                if response and response.get("status") == "cash_out_success":
                    sys.stdout.write("\r" + " " * 70 + "\r")
                    print(f"Cash out realizado com sucesso em {response['multiplier']:.2f}x!")
                    print(f"Você ganhou R${response['winnings']:.2f}! Novo saldo: R${client_balance:.2f}")
                    has_active_bet = False
                else:
                    print(f"Erro no cash out: {response.get('message', 'Cash out falhou') if response else 'Sem resposta'}")
            else:
                print("Não é possível fazer cash out agora (jogo não está 'running' ou não há aposta ativa).")

        elif choice == "3":
            response = send_tcp_command("status")
            if not running_client: break

            if response and response.get("status") == "game_status":
                sys.stdout.write("\r" + " " * 70 + "\r")
                print(f"\n--- Status do Jogo ---")
                print(f"Status no servidor: {response['game_status']}")
                print(f"Multiplicador no servidor: {response['multiplier']:.2f}x")
                print(f"Seu saldo (Jogador: {player_name}): R${client_balance:.2f}")

                if response.get("history"):
                    print("Histórico recente de crashes:")
                    for mult_val in response["history"]: # Renomeado para evitar conflito
                        print(f"  {mult_val:.2f}x")
            else:
                print(f"Erro ao obter status do jogo: {response.get('message', 'Falha') if response else 'Sem resposta'}")
        
        elif choice == "4": # Ver Ranking
            response = send_tcp_command("get_ranking")
            if not running_client: break

            if response and response.get("status") == "ranking_data":
                ranking = response.get("ranking", [])
                sys.stdout.write("\r" + " " * 70 + "\r")
                print("\n--- RANKING DOS MELHORES JOGADORES ---")
                if ranking:
                    for i, player_entry in enumerate(ranking):
                        print(f"{i+1}. {player_entry.get('name', 'N/A')} - R${player_entry.get('balance', 0):.2f}")
                else:
                    print("Nenhum jogador no ranking ainda ou ranking vazio.")
            else:
                print(f"Erro ao obter ranking: {response.get('message', 'Falha ao buscar ranking') if response else 'Sem resposta'}")


        elif choice == "5": # Sair
            print("Saindo do jogo...")
            running_client = False # Sinaliza para sair do loop
            break
            
        else:
            print("Opção inválida. Tente novamente.")

        if running_client: # Só dorme se ainda estiver rodando
            time.sleep(0.1)

except KeyboardInterrupt:
    print("\nPrograma encerrado pelo usuário.")
except ConnectionRefusedError:
    print(f"\nErro: Não foi possível conectar ao servidor em {SERVER_HOST}:{TCP_PORT}. Verifique se o servidor está online.")
except Exception as e:
    print(f"\nOcorreu um erro fatal no cliente: {e}")
finally:
    print("Fechando sockets...")
    running_client = False # Garante que threads saibam que devem parar, se usarem essa flag
    if tcp_socket:
        try:
            tcp_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        tcp_socket.close()
    if udp_socket:
        udp_socket.close()
    print("Cliente encerrado.")