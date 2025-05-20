import socket
import threading
import json
import time
import sys
import pygame
import queue
import math
import random
import os
import io
import urllib.request

# Configurações do cliente
SERVER_HOST = '127.0.0.1'  # Altere para o IP do servidor na rede local
TCP_PORT = 5000
UDP_PORT = 5001

# Configurações da interface
WIDTH, HEIGHT = 800, 600
BACKGROUND_COLOR = (25, 25, 35)
TEXT_COLOR = (255, 255, 255)
GREEN_COLOR = (0, 255, 100)
RED_COLOR = (255, 50, 50)
YELLOW_COLOR = (255, 255, 0)
BUTTON_COLOR = (45, 45, 60)
BUTTON_HOVER_COLOR = (65, 65, 80)
GOLD_COLOR = (255, 215, 0)
SILVER_COLOR = (192, 192, 192)
BRONZE_COLOR = (205, 127, 50)
INPUT_COLOR = (35, 35, 45)
INPUT_ACTIVE_COLOR = (45, 45, 55)
OVERLAY_COLOR = (0, 0, 0, 180)  # Cor semi-transparente para o overlay

# Inicializar Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Blaze Crash - Cliente (Final)")
clock = pygame.time.Clock()

# Carregar fontes
try:
    font = pygame.font.SysFont("Arial", 24)
    font_large = pygame.font.SysFont("Arial", 48)
    font_small = pygame.font.SysFont("Arial", 18)
    font_bold = pygame.font.SysFont("Arial", 24, bold=True)
except:
    print("Erro ao carregar fontes. Usando fontes padrão.")
    font = pygame.font.Font(None, 24)
    font_large = pygame.font.Font(None, 48)
    font_small = pygame.font.Font(None, 18)
    font_bold = font

# Carregar imagem de confirmação de saída
exit_image = None
try:
    # Verificar se a imagem existe no diretório atual
    if os.path.exists("exit_image.png"):
        exit_image = pygame.image.load("exit_image.png")
    else:
        # Baixar a imagem da URL
        url = "https://hebbkx1anhila5yf.public.blob.vercel-storage.com/image-HzZaykJ1cSdYvXRaTt60syD9l3dZUq.png"
        print(f"Baixando imagem de {url}...")
        
        with urllib.request.urlopen(url) as response:
            image_data = response.read()
        
        # Salvar a imagem localmente para uso futuro
        with open("exit_image.png", "wb") as f:
            f.write(image_data)
        
        # Carregar a imagem a partir dos dados baixados
        image_file = io.BytesIO(image_data)
        exit_image = pygame.image.load(image_file)
    
    # Redimensionar a imagem para caber na tela
    exit_image = pygame.transform.scale(exit_image, (400, 200))
except Exception as e:
    print(f"Erro ao carregar imagem de saída: {e}")
    exit_image = None

# Fila para comunicação entre threads
update_queue = queue.Queue()

# Variáveis de estado do cliente
current_multiplier = 1.0
game_status = "waiting"
has_active_bet = False
bet_amount = 0
balance = 1000  # Saldo inicial fictício
history = []
message = "Iniciando..."
message_timer = 3000
last_update_time = time.time()
debug_info = []
connection_active = False

# Variáveis para entrada de nome
default_name = f"Jogador_{random.randint(1000, 9999)}"
player_name = ""
name_input_active = True
name_input_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2, 300, 40)
name_input_text = ""
name_confirmed = False
name_error = ""

# Variáveis para confirmação de saída
show_exit_confirmation = False
exit_confirmation_rect = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 150, 400, 300)
exit_yes_button = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 + 100, 100, 40)
exit_no_button = pygame.Rect(WIDTH // 2 + 20, HEIGHT // 2 + 100, 100, 40)

# Ranking (exemplo)
leaderboard = [
    {"name": default_name, "balance": balance},
    {"name": "Bot1", "balance": 800},
    {"name": "Bot2", "balance": 750},
    {"name": "Bot3", "balance": 600},
    {"name": "Bot4", "balance": 500}
]

# Valores de aposta predefinidos
bet_values = [10, 50, 100, 200]
bet_buttons = []
button_width = 100
button_spacing = 20
total_buttons_width = (button_width * len(bet_values)) + (button_spacing * (len(bet_values) - 1))
start_x = (WIDTH - total_buttons_width) // 2

for i, value in enumerate(bet_values):
    bet_buttons.append(pygame.Rect(start_x + i * (button_width + button_spacing), 400, button_width, 50))

# Botão de apostar tudo
all_in_button = pygame.Rect(WIDTH // 2 - 50, 460, 100, 40)

# Botão de cash out
cashout_button = pygame.Rect(WIDTH // 2 - 100, 510, 200, 50)

# Botão para confirmar nome
confirm_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 60, 200, 40)

# Inicializar sockets
tcp_socket = None
udp_socket = None

# Função para verificar se o nome do jogador já existe
def check_player_name():
    global player_name, balance, name_error, message, message_timer
    
    if not tcp_socket:
        return False
    
    try:
        message_data = {"command": "check_name", "player_name": player_name}
        tcp_socket.send(json.dumps(message_data).encode('utf-8'))
        response = tcp_socket.recv(1024)
        response_data = json.loads(response.decode('utf-8'))
        
        if response_data["status"] == "ok":
            balance = response_data["balance"]
            if "message" in response_data:
                message = response_data["message"]
                message_timer = 3000
            return True
        else:
            name_error = response_data.get("message", "Nome inválido ou já em uso.")
            return False
    except Exception as e:
        print(f"Erro ao verificar nome: {e}")
        name_error = f"Erro ao verificar nome: {e}"
        return False

# Função para conectar ao servidor
def connect_to_server():
    global tcp_socket, udp_socket, connection_active, message, message_timer, player_name
    
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Configurar timeout para o socket UDP para não bloquear
        udp_socket.settimeout(0.1)
        
        # Conectar ao servidor
        tcp_socket.connect((SERVER_HOST, TCP_PORT))
        print(f"Conectado ao servidor {SERVER_HOST}:{TCP_PORT}")
        
        # Verificar se o nome do jogador já existe
        if not check_player_name():
            tcp_socket.close()
            udp_socket.close()
            tcp_socket = None
            udp_socket = None
            return False
        
        # Configurar socket UDP para receber atualizações
        udp_socket.bind(('', 0))  # Usar '' em vez de '0.0.0.0'
        udp_addr = udp_socket.getsockname()
        print(f"Socket UDP vinculado a {udp_addr}")
        
        # Registrar o endereço UDP no servidor
        register_message = {
            "command": "register_udp",
            "udp_addr": udp_addr,
            "player_name": player_name
        }
        tcp_socket.send(json.dumps(register_message).encode('utf-8'))
        response = tcp_socket.recv(1024)
        print(f"Resposta do registro UDP: {response.decode('utf-8')}")
        
        message = f"Conectado ao servidor {SERVER_HOST}"
        message_timer = 3000
        connection_active = True
        
        # Iniciar thread UDP
        udp_thread = threading.Thread(target=receive_udp_updates, daemon=True)
        udp_thread.start()
        
        # Obter status inicial
        if not get_game_status():
            message = "Erro ao obter status inicial do jogo"
            message_timer = 3000
            
        return True
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        message = f"Erro ao conectar: {e}"
        message_timer = 5000
        if tcp_socket:
            tcp_socket.close()
        if udp_socket:
            udp_socket.close()
        tcp_socket = None
        udp_socket = None
        return False

# Função para receber atualizações UDP
def receive_udp_updates():
    global update_queue, connection_active
    
    if not udp_socket:
        return
        
    print("Thread UDP iniciada")
    while connection_active:
        try:
            # Usar timeout para não bloquear indefinidamente
            data, _ = udp_socket.recvfrom(1024)
            update = json.loads(data.decode('utf-8'))
            
            # Colocar a atualização na fila para ser processada pelo loop principal
            update_queue.put(update)
            
        except socket.timeout:
            # Timeout é normal, continua o loop
            continue
        except Exception as e:
            print(f"Erro ao receber atualização UDP: {e}")
            update_queue.put({"error": str(e)})
            time.sleep(1)  # Esperar um pouco antes de tentar novamente
    
    print("Thread UDP encerrada")

# Função para processar atualizações da fila
def process_updates():
    global current_multiplier, game_status, last_update_time, debug_info, has_active_bet, history, leaderboard, message, message_timer
    
    # Processar todas as atualizações na fila
    updates_processed = 0
    while not update_queue.empty():
        update = update_queue.get()
        updates_processed += 1
        
        if "error" in update:
            message = f"Erro na conexão UDP: {update['error']}"
            message_timer = 3000
            continue
        
        # Atualizar leaderboard se disponível
        if "leaderboard" in update:
            leaderboard = update["leaderboard"]
            
        current_multiplier = update["multiplier"]
        new_status = update["status"]
        
        # Se o jogo acabou de crashar, adicione ao histórico e verifique se o jogador perdeu
        if new_status == "crashed" and game_status == "running":
            history.append(current_multiplier)
            if len(history) > 8:  # Limitando a 8 itens para caber na tela
                history.pop(0)
            
            # Se o jogador tinha uma aposta ativa e não fez cash out, ele perdeu
            if has_active_bet:
                print(f"Você perdeu {bet_amount:.2f} no crash em {current_multiplier:.2f}x")
                message = f"Você perdeu {bet_amount:.2f} no crash em {current_multiplier:.2f}x"
                message_timer = 3000
                has_active_bet = False
        
        # Se o jogo estava crashed e agora está waiting, reinicia para nova rodada
        if game_status == "crashed" and new_status == "waiting":
            print("Nova rodada iniciando")
        
        game_status = new_status
        last_update_time = time.time()
        
        # Adicionar à informação de depuração
        debug_info.append(f"Update: {game_status} - {current_multiplier:.2f}x")
        if len(debug_info) > 5:
            debug_info.pop(0)
    
    return updates_processed

# Função para enviar comandos TCP
def send_tcp_command(command, **kwargs):
    global message, message_timer
    
    if not tcp_socket:
        message = "Não conectado ao servidor"
        message_timer = 3000
        return None
        
    message_data = {"command": command, "player_name": player_name, **kwargs}
    try:
        print(f"Enviando comando: {message_data}")
        tcp_socket.send(json.dumps(message_data).encode('utf-8'))
        response = tcp_socket.recv(1024)
        response_data = json.loads(response.decode('utf-8'))
        print(f"Resposta recebida: {response_data}")
        return response_data
    except Exception as e:
        print(f"Erro ao enviar comando: {e}")
        message = f"Erro ao enviar comando: {e}"
        message_timer = 3000
        return None

# Função para obter status inicial e histórico
def get_game_status():
    global history, message, message_timer, game_status, current_multiplier, leaderboard
    
    response = send_tcp_command("status")
    if response and response["status"] == "game_status":
        history = response["history"]
        game_status = response["game_status"]
        current_multiplier = response["multiplier"]
        if "leaderboard" in response:
            leaderboard = response["leaderboard"]
        message = "Status do jogo atualizado"
        message_timer = 2000
        print(f"Status do jogo: {game_status}, Multiplicador: {current_multiplier:.2f}x")
        return True
    return False

# Função para desenhar texto
def draw_text(text, font, color, x, y):
    # Garantir que a cor seja válida
    if isinstance(color, tuple) and len(color) == 3:
        # Garantir que todos os componentes da cor estejam entre 0 e 255
        r = max(0, min(255, int(color[0])))
        g = max(0, min(255, int(color[1])))
        b = max(0, min(255, int(color[2])))
        color = (r, g, b)
    else:
        # Se a cor não for válida, usar uma cor padrão
        color = TEXT_COLOR
    
    try:
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.topleft = (x, y)
        screen.blit(text_surface, text_rect)
    except Exception as e:
        print(f"Erro ao renderizar texto '{text}': {e}")

# Função para desenhar botão
def draw_button(rect, text, enabled=True):
    mouse_pos = pygame.mouse.get_pos()
    is_hover = rect.collidepoint(mouse_pos)
    is_clicked = False
    
    if not enabled:
        color = (80, 80, 80)  # Cinza escuro para botões desativados
    elif is_hover:
        color = BUTTON_HOVER_COLOR
        if pygame.mouse.get_pressed()[0]:
            is_clicked = True
    else:
        color = BUTTON_COLOR
    
    pygame.draw.rect(screen, color, rect, border_radius=5)
    
    text_surface = font.render(text, True, TEXT_COLOR)
    text_rect = text_surface.get_rect(center=rect.center)
    screen.blit(text_surface, text_rect)
    
    return is_hover and is_clicked and enabled

# Função para calcular cor pulsante de forma segura
def get_pulse_color(base_color, intensity=0.2):
    try:
        pulse = (math.sin(time.time() * 5) + 1) * intensity + (1 - intensity)
        r = max(0, min(255, int(base_color[0] * pulse)))
        g = max(0, min(255, int(base_color[1] * pulse)))
        b = max(0, min(255, int(base_color[2] * pulse)))
        return (r, g, b)
    except Exception as e:
        print(f"Erro ao calcular cor pulsante: {e}")
        return base_color  # Retorna a cor base em caso de erro

# Função para desenhar a tela de entrada de nome
def draw_name_input_screen():
    global name_input_text, name_input_active, name_confirmed, player_name, name_error
    
    # Limpar a tela
    screen.fill(BACKGROUND_COLOR)
    
    # Desenhar título
    draw_text("CRASH GAME", font_large, TEXT_COLOR, WIDTH//2 - 150, 100)
    
    # Desenhar instruções
    draw_text("Digite seu nome para jogar:", font, TEXT_COLOR, WIDTH//2 - 150, HEIGHT//2 - 50)
    
    # Desenhar campo de entrada
    color = INPUT_ACTIVE_COLOR if name_input_active else INPUT_COLOR
    pygame.draw.rect(screen, color, name_input_rect, border_radius=5)
    
    # Mostrar texto digitado ou placeholder
    if name_input_text:
        draw_text(name_input_text, font, TEXT_COLOR, name_input_rect.x + 10, name_input_rect.y + 10)
    else:
        draw_text(default_name, font, (150, 150, 150), name_input_rect.x + 10, name_input_rect.y + 10)
    
    # Desenhar cursor piscante se o campo estiver ativo
    if name_input_active and int(time.time() * 2) % 2 == 0:
        cursor_pos = name_input_rect.x + 10 + font.size(name_input_text)[0]
        pygame.draw.line(screen, TEXT_COLOR, 
                         (cursor_pos, name_input_rect.y + 10), 
                         (cursor_pos, name_input_rect.y + 30), 2)
    
    # Desenhar mensagem de erro se houver
    if name_error:
        draw_text(name_error, font_small, RED_COLOR, WIDTH//2 - 150, HEIGHT//2 + 120)
    else:
        # Desenhar mensagem de ajuda
        draw_text("Deixe em branco para usar nome aleatório", font_small, (150, 150, 150), WIDTH//2 - 150, HEIGHT//2 + 120)
    
    # Desenhar botão de confirmação
    confirm_clicked = draw_button(confirm_button, "CONFIRMAR")
    if confirm_clicked:
        if name_input_text:
            player_name = name_input_text
        else:
            player_name = default_name
        
        # Tentar conectar ao servidor e verificar o nome
        if connect_to_server():
            name_confirmed = True
            return True
    
    return False

# Função para desenhar a tela de confirmação de saída
def draw_exit_confirmation():
    # Criar uma superfície semi-transparente para o overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))  # Preto semi-transparente
    screen.blit(overlay, (0, 0))
    
    # Desenhar o fundo da caixa de diálogo
    pygame.draw.rect(screen, BACKGROUND_COLOR, exit_confirmation_rect, border_radius=10)
    
    # Desenhar a imagem
    if exit_image:
        image_rect = exit_image.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
        screen.blit(exit_image, image_rect)
    
    # Desenhar a mensagem
    draw_text("Tem certeza que vai parar agora?", font_bold, YELLOW_COLOR, WIDTH // 2 - 180, HEIGHT // 2 + 50)
    
    # Desenhar os botões
    yes_clicked = draw_button(exit_yes_button, "SIM")
    no_clicked = draw_button(exit_no_button, "NÃO")
    
    return yes_clicked, no_clicked

# Loop principal
running = True
show_debug = False  # Iniciar com depuração desativada
frame_count = 0
last_fps_update = time.time()
fps = 0
reconnect_timer = 0

# Loop principal
while running:
    # Limitar a taxa de quadros
    clock.tick(60)
    
    # Processar eventos
    for event in pygame.event.get():
        # Verificar se o usuário está tentando fechar a janela
        if event.type == pygame.QUIT:
            if show_exit_confirmation:
                running = False  # Se já estiver mostrando a confirmação, fechar
            else:
                show_exit_confirmation = True  # Mostrar confirmação antes de fechar
                continue
        
        # Se estiver mostrando a confirmação de saída, processar apenas eventos relacionados a ela
        if show_exit_confirmation:
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if exit_yes_button.collidepoint(mouse_pos):
                    running = False
                elif exit_no_button.collidepoint(mouse_pos):
                    show_exit_confirmation = False
            continue
        
        # Eventos para a tela de entrada de nome
        if not name_confirmed:
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Verificar se clicou no campo de texto
                if name_input_rect.collidepoint(event.pos):
                    name_input_active = True
                else:
                    name_input_active = False
                
                # Verificar se clicou no botão de confirmação
                if confirm_button.collidepoint(event.pos):
                    if name_input_text:
                        player_name = name_input_text
                    else:
                        player_name = default_name
                    
                    # Tentar conectar ao servidor e verificar o nome
                    if connect_to_server():
                        name_confirmed = True
            
            # Processar entrada de texto
            if event.type == pygame.KEYDOWN:
                if name_input_active:
                    if event.key == pygame.K_RETURN:
                        if name_input_text:
                            player_name = name_input_text
                        else:
                            player_name = default_name
                        
                        # Tentar conectar ao servidor e verificar o nome
                        if connect_to_server():
                            name_confirmed = True
                    elif event.key == pygame.K_BACKSPACE:
                        name_input_text = name_input_text[:-1]
                        name_error = ""  # Limpar mensagem de erro ao editar
                    else:
                        # Limitar o tamanho do nome e aceitar apenas caracteres válidos
                        if len(name_input_text) < 15 and event.unicode.isprintable():
                            name_input_text += event.unicode
                            name_error = ""  # Limpar mensagem de erro ao editar
        
        # Eventos para o jogo principal
        else:
            # Alternar modo de depuração com a tecla D
            if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                show_debug = not show_debug
            
            # Reconectar com a tecla R
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                message = "Tentando reconectar..."
                message_timer = 3000
                reconnect_timer = 3  # Reconectar em 3 segundos
            
            # Forçar cash out com a tecla C (para testes)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                if game_status == "running" and has_active_bet:
                    print("Tentando cash out forçado...")
                    response = send_tcp_command("cash_out")
                    
                    if response and response["status"] == "cash_out_success":
                        winnings = response["winnings"]
                        cash_out_multiplier = response["multiplier"]
                        message = f"Cash out em {cash_out_multiplier:.2f}x! Ganhou {winnings:.2f}!"
                        message_timer = 3000
                        has_active_bet = False
                        balance += winnings
                        
                        # Atualizar o saldo no leaderboard local
                        for player in leaderboard:
                            if player["name"] == player_name:
                                player["balance"] = balance
                                break
                        
                        print(f"Cash out em {cash_out_multiplier:.2f}x! Ganhou {winnings:.2f}!")
                    else:
                        message = f"Erro: {response.get('message', 'Cash out falhou')}"
                        message_timer = 3000
            
            # Verificar cliques nos botões
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Botões de aposta predefinida
                if game_status == "waiting" and not has_active_bet:
                    for i, button in enumerate(bet_buttons):
                        if button.collidepoint(event.pos):
                            bet_value = bet_values[i]
                            if bet_value <= balance:
                                response = send_tcp_command("bet", amount=bet_value)
                                
                                if response and response["status"] == "bet_accepted":
                                    message = f"Aposta de {bet_value} aceita!"
                                    message_timer = 3000
                                    has_active_bet = True
                                    bet_amount = bet_value
                                    balance -= bet_value
                                    
                                    # Atualizar o saldo no leaderboard local
                                    for player in leaderboard:
                                        if player["name"] == player_name:
                                            player["balance"] = balance
                                            break
                                    
                                    print(f"Aposta de {bet_value} aceita!")
                                else:
                                    message = f"Erro: {response.get('message', 'Aposta não aceita')}"
                                    message_timer = 3000
                            else:
                                message = "Saldo insuficiente"
                                message_timer = 3000
                    
                    # Botão de apostar tudo
                    if all_in_button.collidepoint(event.pos):
                        if balance > 0:
                            response = send_tcp_command("bet", amount="all")
                            
                            if response and response["status"] == "bet_accepted":
                                bet_value = response["amount"]
                                message = f"Aposta de {bet_value} aceita! (ALL IN)"
                                message_timer = 3000
                                has_active_bet = True
                                bet_amount = bet_value
                                balance = 0  # Zerar o saldo localmente
                                
                                # Atualizar o saldo no leaderboard local
                                for player in leaderboard:
                                    if player["name"] == player_name:
                                        player["balance"] = 0
                                        break
                                
                                print(f"Aposta de {bet_value} aceita! (ALL IN)")
                            else:
                                message = f"Erro: {response.get('message', 'Aposta não aceita')}"
                                message_timer = 3000
                        else:
                            message = "Saldo insuficiente"
                            message_timer = 3000
                
                # Botão de cash out
                if cashout_button.collidepoint(event.pos):
                    if game_status == "running" and has_active_bet:
                        print("Tentando cash out...")
                        response = send_tcp_command("cash_out")
                        
                        if response and response["status"] == "cash_out_success":
                            winnings = response["winnings"]
                            cash_out_multiplier = response["multiplier"]
                            message = f"Cash out em {cash_out_multiplier:.2f}x! Ganhou {winnings:.2f}!"
                            message_timer = 3000
                            has_active_bet = False
                            balance += winnings
                            
                            # Atualizar o saldo no leaderboard local
                            for player in leaderboard:
                                if player["name"] == player_name:
                                    player["balance"] = balance
                                    break
                            
                            print(f"Cash out em {cash_out_multiplier:.2f}x! Ganhou {winnings:.2f}!")
                        else:
                            message = f"Erro: {response.get('message', 'Cash out falhou')}"
                            message_timer = 3000
                    else:
                        message = "Cash out não disponível"
                        message_timer = 3000
                        print(f"Cash out não disponível. Status: {game_status}, Aposta ativa: {has_active_bet}")
    
    # Se estiver mostrando a confirmação de saída, desenhar apenas ela
    if show_exit_confirmation:
        # Primeiro desenhar o jogo normal como fundo
        if not name_confirmed:
            draw_name_input_screen()
        else:
            # Desenhar a tela do jogo normalmente
            screen.fill(BACKGROUND_COLOR)
            
            # Desenhar título
            draw_text("CRASH GAME", font_large, TEXT_COLOR, WIDTH//2 - 150, 50)
            
            # Desenhar multiplicador atual
            if game_status == "running":
                multiplier_color = get_pulse_color(GREEN_COLOR)
            elif game_status == "crashed":
                multiplier_color = RED_COLOR
            else:
                multiplier_color = YELLOW_COLOR
                
            draw_text(f"{current_multiplier:.2f}x", font_large, multiplier_color, WIDTH//2 - 80, 150)
            
            # Desenhar status do jogo
            status_text = "AGUARDANDO APOSTAS" if game_status == "waiting" else ("EM ANDAMENTO" if game_status == "running" else "CRASH!")
            draw_text(status_text, font, TEXT_COLOR, WIDTH//2 - 120, 220)
            
            # Desenhar saldo e nome
            draw_text(f"Saldo: {balance:.2f}", font, TEXT_COLOR, 50, 50)
            draw_text(f"Jogador: {player_name}", font_small, TEXT_COLOR, 50, 80)
            
            # Desenhar histórico
            pygame.draw.rect(screen, (35, 35, 45), (WIDTH - 200, 50, 180, 300), border_radius=5)
            draw_text("HISTÓRICO", font, TEXT_COLOR, WIDTH - 180, 60)
            
            # Desenhar ranking
            pygame.draw.rect(screen, (35, 35, 45), (50, 170, 200, 170), border_radius=5)
            draw_text("RANKING", font_bold, TEXT_COLOR, 60, 180)
        
        # Agora desenhar a confirmação de saída por cima
        draw_exit_confirmation()
        
        pygame.display.flip()
        continue
    
    # Se ainda estiver na tela de entrada de nome
    if not name_confirmed:
        draw_name_input_screen()
    else:
        # Processar atualizações da fila
        if connection_active:
            updates = process_updates()
            if updates > 0:
                print(f"Processadas {updates} atualizações")
        
        # Verificar se precisa reconectar
        if reconnect_timer > 0:
            reconnect_timer -= clock.get_time() / 1000
            if reconnect_timer <= 0:
                connect_to_server()
        
        # Calcular FPS
        frame_count += 1
        if time.time() - last_fps_update >= 1.0:
            fps = frame_count
            frame_count = 0
            last_fps_update = time.time()
        
        # Limpar a tela
        screen.fill(BACKGROUND_COLOR)
        
        # Desenhar título
        draw_text("CRASH GAME", font_large, TEXT_COLOR, WIDTH//2 - 150, 50)
        
        # Desenhar multiplicador atual com animação pulsante se o jogo estiver em andamento
        if game_status == "running":
            # Usar função segura para calcular cor pulsante
            multiplier_color = get_pulse_color(GREEN_COLOR)
        elif game_status == "crashed":
            multiplier_color = RED_COLOR
        else:
            multiplier_color = YELLOW_COLOR
            
        draw_text(f"{current_multiplier:.2f}x", font_large, multiplier_color, WIDTH//2 - 80, 150)
        
        # Desenhar status do jogo
        status_text = "AGUARDANDO APOSTAS" if game_status == "waiting" else ("EM ANDAMENTO" if game_status == "running" else "CRASH!")
        draw_text(status_text, font, TEXT_COLOR, WIDTH//2 - 120, 220)
        
        # Desenhar saldo
        draw_text(f"Saldo: {balance:.2f}", font, TEXT_COLOR, 50, 50)
        
        # Desenhar nome do jogador
        draw_text(f"Jogador: {player_name}", font_small, TEXT_COLOR, 50, 80)
        
        # Desenhar aposta atual
        if has_active_bet:
            draw_text(f"Aposta: {bet_amount:.2f}", font, TEXT_COLOR, 50, 110)
            potential_win = bet_amount * current_multiplier
            draw_text(f"Potencial: {potential_win:.2f}", font, GREEN_COLOR, 50, 140)
        
        # Desenhar botões de aposta predefinida
        if game_status == "waiting" and not has_active_bet:
            draw_text("Escolha um valor para apostar:", font, TEXT_COLOR, WIDTH//2 - 150, 350)
            for i, button in enumerate(bet_buttons):
                draw_button(button, f"{bet_values[i]}", bet_values[i] <= balance)
            
            # Desenhar botão de apostar tudo
            draw_button(all_in_button, "ALL IN", balance > 0)
        
        # Desenhar botão de cash out
        cashout_enabled = game_status == "running" and has_active_bet
        draw_button(cashout_button, "CASH OUT", cashout_enabled)
        
        # Desenhar histórico (ajustado para não ultrapassar o quadrado)
        history_rect = pygame.Rect(WIDTH - 200, 50, 180, 300)
        pygame.draw.rect(screen, (35, 35, 45), history_rect, border_radius=5)
        draw_text("HISTÓRICO", font, TEXT_COLOR, WIDTH - 180, 60)
        
        # Limitar o número de itens no histórico para caber na área
        visible_history = history[:8]  # Mostrar apenas os 8 mais recentes
        for i, mult in enumerate(reversed(visible_history)):
            color = RED_COLOR if mult < 2.0 else GREEN_COLOR
            # Garantir que o texto fique dentro do retângulo
            draw_text(f"{mult:.2f}x", font, color, WIDTH - 160, 100 + i * 30)
        
        # Desenhar ranking (movido para o canto superior esquerdo)
        leaderboard_rect = pygame.Rect(50, 170, 200, 170)
        pygame.draw.rect(screen, (35, 35, 45), leaderboard_rect, border_radius=5)
        draw_text("RANKING", font_bold, TEXT_COLOR, 60, 180)
        
        # Ordenar o leaderboard por saldo
        sorted_leaderboard = sorted(leaderboard, key=lambda x: x["balance"], reverse=True)
        
        # Mostrar os top 5
        for i, player in enumerate(sorted_leaderboard[:5]):
            # Escolher cor baseada na posição
            if i == 0:
                name_color = GOLD_COLOR
            elif i == 1:
                name_color = SILVER_COLOR
            elif i == 2:
                name_color = BRONZE_COLOR
            else:
                name_color = TEXT_COLOR
                
            # Destacar o jogador atual
            if player["name"] == player_name:
                pygame.draw.rect(screen, (50, 50, 70), (55, 210 + i * 30, 190, 25), border_radius=3)
                
            # Truncar nomes longos
            display_name = player["name"]
            if len(display_name) > 10:
                display_name = display_name[:10] + ".."
                
            draw_text(f"{i+1}. {display_name}", font_small, name_color, 60, 210 + i * 30)
            draw_text(f"{player['balance']:.0f}", font_small, TEXT_COLOR, 200, 210 + i * 30)
        
        # Desenhar mensagem temporária
        if message_timer > 0:
            draw_text(message, font, YELLOW_COLOR, WIDTH//2 - 200, HEIGHT - 50)
            message_timer -= clock.get_time()
        
        # Desenhar informações de depuração se ativado
        if show_debug:
            pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - 150, WIDTH, 150))
            draw_text(f"FPS: {fps}", font_small, TEXT_COLOR, 10, HEIGHT - 140)
            draw_text(f"Última atualização: {time.time() - last_update_time:.2f}s atrás", font_small, TEXT_COLOR, 10, HEIGHT - 120)
            draw_text(f"Status do jogo: {game_status}", font_small, TEXT_COLOR, 10, HEIGHT - 100)
            draw_text(f"Multiplicador: {current_multiplier:.2f}x", font_small, TEXT_COLOR, 10, HEIGHT - 80)
            draw_text(f"Aposta ativa: {'Sim' if has_active_bet else 'Não'}", font_small, TEXT_COLOR, 10, HEIGHT - 60)
            draw_text(f"Nome: {player_name}", font_small, TEXT_COLOR, 10, HEIGHT - 40)
            
            for i, info in enumerate(debug_info):
                draw_text(info, font_small, TEXT_COLOR, 300, HEIGHT - 140 + i * 20)
            
            # Dica para cash out rápido
            draw_text("Pressione C para cash out rápido", font_small, GREEN_COLOR, 300, HEIGHT - 40)
        else:
            # Mostrar dica para ativar depuração
            draw_text("Pressione D para depuração", font_small, (100, 100, 100), 10, HEIGHT - 20)
        
        # Indicador de conexão
        connection_color = GREEN_COLOR if connection_active and time.time() - last_update_time < 2.0 else RED_COLOR
        pygame.draw.circle(screen, connection_color, (WIDTH - 20, 20), 10)
    
    # Atualizar a tela
    pygame.display.flip()

# Encerrar conexões
connection_active = False
if tcp_socket:
    tcp_socket.close()
if udp_socket:
    udp_socket.close()
pygame.quit()
sys.exit()