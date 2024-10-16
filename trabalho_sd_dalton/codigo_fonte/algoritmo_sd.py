import os
import socket
import threading
import time
import random
from datetime import datetime
import pytz
from filelock import FileLock

# Variáveis de configuração
ID_DISPOSITIVO = int(os.environ.get('DEVICE_ID'))  # ID do dispositivo a partir da variável de ambiente
PORTAS = {1: 5001, 2: 5002, 3: 5003, 4: 5004}  # Portas para comunicação entre dispositivos
HOSTS = {1: 'node1', 2: 'node2', 3: 'node3', 4: 'node4'}  # Renomeando dispositivos

# Caminhos do arquivo de logs e do bloqueio
ARQUIVO_LOG = "/app/logs/access_log.txt"
ARQUIVO_BLOQUEIO = "/app/logs/access_lock.lock"

# Variáveis globais de controle
acessando_dados = False
fila_solicitacoes = []
permissoes_recebidas = 0
hora_solicitacao = None
NUM_DISPOSITIVOS = len(PORTAS) - 1

# Configuração de fuso horário
FUSO_HORARIO_BRASIL = pytz.timezone('America/Sao_Paulo')

def registrar_acesso():
    """
    Função para gravar no log o acesso ao recurso compartilhado.
    """
    global acessando_dados
    acessando_dados = True  # Indica que o dispositivo está utilizando o dado

    bloqueio = FileLock(ARQUIVO_BLOQUEIO)
    with bloqueio:
        with open(ARQUIVO_LOG, 'a') as log_file:
            timestamp = datetime.now(FUSO_HORARIO_BRASIL).strftime('%Y-%m-%d %H:%M:%S')
            log_file.write(f"Dispositivo {ID_DISPOSITIVO} acessou o dado compartilhado às {timestamp}\n")

        print(f"Dispositivo {ID_DISPOSITIVO} está usando o dado compartilhado.", flush=True)
        time.sleep(10)  # Simula o tempo de uso do dado
        print(f"Dispositivo {ID_DISPOSITIVO} terminou de usar o dado compartilhado.", flush=True)

    finalizar_acesso()

def enviar_solicitacao():
    """
    Envia uma solicitação de acesso ao dado compartilhado para outros dispositivos.
    """
    global hora_solicitacao, permissoes_recebidas
    hora_solicitacao = time.time()
    permissoes_recebidas = 0
    fila_solicitacoes.clear()

    print(f"Dispositivo {ID_DISPOSITIVO} solicitou acesso ao dado compartilhado às {hora_solicitacao}", flush=True)

    for id_disp, porta in PORTAS.items():
        if id_disp != ID_DISPOSITIVO:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((HOSTS[id_disp], porta))
                    mensagem = f"REQ:{ID_DISPOSITIVO}:{hora_solicitacao}"
                    sock.sendall(mensagem.encode())
            except Exception as e:
                print(f"Erro ao enviar solicitação para Dispositivo {id_disp}: {e}", flush=True)

    while permissoes_recebidas < NUM_DISPOSITIVOS:
        time.sleep(1)

    registrar_acesso()

def finalizar_acesso():
    """
    Libera o recurso compartilhado e gerencia a fila de dispositivos que solicitaram acesso.
    """
    global fila_solicitacoes
    while fila_solicitacoes:
        proximo_dispositivo, _ = fila_solicitacoes.pop(0)
        conceder_permissao(proximo_dispositivo)
    print(f"Dispositivo {ID_DISPOSITIVO} liberou o dado compartilhado.", flush=True)

def conceder_permissao(id_dispositivo):
    """
    Envia uma permissão de acesso ao dispositivo especificado.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HOSTS[id_dispositivo], PORTAS[id_dispositivo]))
            mensagem = f"GRANT:{ID_DISPOSITIVO}"
            sock.sendall(mensagem.encode())
    except Exception as e:
        print(f"Falha ao enviar permissão para Dispositivo {id_dispositivo}: {e}", flush=True)

def processar_mensagem(mensagem, endereco):
    """
    Processa as mensagens recebidas, que podem ser solicitações ou permissões.
    """
    global fila_solicitacoes, permissoes_recebidas, acessando_dados

    partes_mensagem = mensagem.split(':')
    tipo_mensagem = partes_mensagem[0]

    if tipo_mensagem == 'REQ':
        id_solicitante, hora_solicitacao_solicitante = int(partes_mensagem[1]), float(partes_mensagem[2])

        if acessando_dados or (hora_solicitacao and
                               (hora_solicitacao < hora_solicitacao_solicitante or
                                (hora_solicitacao == hora_solicitacao_solicitante and ID_DISPOSITIVO < id_solicitante))):
            fila_solicitacoes.append((id_solicitante, hora_solicitacao_solicitante))
            print(f"Dispositivo {ID_DISPOSITIVO} colocou o Dispositivo {id_solicitante} na fila. Fila: {fila_solicitacoes}", flush=True)
        else:
            conceder_permissao(id_solicitante)
            print(f"Dispositivo {ID_DISPOSITIVO} concedeu acesso ao Dispositivo {id_solicitante}.", flush=True)

    elif tipo_mensagem == 'GRANT':
        permissoes_recebidas += 1
        print(f"Dispositivo {ID_DISPOSITIVO} recebeu permissão do Dispositivo {partes_mensagem[1]}.", flush=True)

def iniciar_servidor():
    """
    Inicia o servidor TCP para receber conexões de outros dispositivos.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(('0.0.0.0', PORTAS[ID_DISPOSITIVO]))
        server.listen()
        print(f"Dispositivo {ID_DISPOSITIVO} aguardando conexões...", flush=True)

        while True:
            conexao, endereco = server.accept()
            with conexao:
                dados = conexao.recv(1024)
                if dados:
                    processar_mensagem(dados.decode(), endereco)

def iniciar_cliente():
    """
    Dispositivo envia solicitações periodicamente para acessar o dado compartilhado.
    """
    while True:
        enviar_solicitacao()
        time.sleep(random.randint(4, 6))

def principal():
    """
    Inicializa o servidor e cliente em threads separadas.
    """
    thread_servidor = threading.Thread(target=iniciar_servidor)
    thread_servidor.start()

    time.sleep(random.randint(1, 10))

    thread_cliente = threading.Thread(target=iniciar_cliente)
    thread_cliente.start()

if __name__ == "__main__":
    principal()
