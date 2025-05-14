import Pyro5.api
import Pyro5.server
import threading
import time
import os
import random
import socket

@Pyro5.api.expose
class Peer:
    def __init__(self, nome, arquivos):
        self.nome = nome
        self.arquivos = arquivos
        self.tracker_uri = None
        self.epoch = 0
        self.votou_na_epoca = set()
        self.recebeu_heartbeat = True
        self.e_tracker = False
        self.em_eleicao = False
        self.vivos = {}  # nome_peer -> timestamp do último heartbeat

    def listar_arquivos(self):
        return self.arquivos

    def adicionar_arquivo(self, nome_arquivo):
        if nome_arquivo not in self.arquivos:
            self.arquivos.append(nome_arquivo)

            if self.e_tracker:
                print(f"[{self.nome}] Atualizando índice com novo arquivo: {nome_arquivo}")
                # aqui você pode atualizar um dicionário de índice local se quiser
            elif self.tracker_uri:
                try:
                    tracker = Pyro5.api.Proxy(self.tracker_uri)
                    tracker.receber_arquivo(self.nome, nome_arquivo)
                    print(f"[{self.nome}] Avisou o tracker sobre novo arquivo: {nome_arquivo}")
                except Exception as e:
                    print(f"[{self.nome}] Erro ao avisar o tracker: {e}")


    def heartbeat(self):
        self.recebeu_heartbeat = True
        if self.e_tracker:
            self.vivos[self.nome] = time.time()  # opcional
        else:
            # Envia ao tracker
            try:
                tracker = Pyro5.api.Proxy(self.tracker_uri)
                tracker.registrar_heartbeat(self.nome)
            except:
                pass

    def registrar_tracker(self, uri, epoch):
        self.tracker_uri = uri
        self.epoch = epoch
        print(f"[{self.nome}] Novo tracker registrado: {uri} (época {epoch})")

    def registrar_heartbeat(self, nome_peer):
        if self.e_tracker:
            self.vivos[nome_peer] = time.time()

    def consultar_arquivo(self, nome_arquivo):
        if self.e_tracker:
            resultado = [p for p, lista in self.indice.items() if nome_arquivo in lista]
            print(f"[TRACKER {self.nome}] Consulta: '{nome_arquivo}' encontrado em: {resultado}")
            return resultado
        return None

    def votar(self, candidato, epoca):
        if epoca not in self.votou_na_epoca:
            self.votou_na_epoca.add(epoca)
            return True
        return False

def iniciar_peer(nome_peer):
    pasta_arquivos = os.path.join("arquivos", nome_peer)
    os.makedirs(pasta_arquivos, exist_ok=True)
    arquivos = os.listdir(pasta_arquivos)

    peer = Peer(nome_peer, arquivos)

    # Adicionar os arquivos existentes ao peer
    for arquivo in arquivos:
        peer.adicionar_arquivo(arquivo)  # Aqui adicionamos os arquivos já existentes

    daemon = Pyro5.api.Daemon(host=socket.gethostbyname(socket.gethostname()))
    uri = daemon.register(peer)

    ns = Pyro5.api.locate_ns()
    ns.register(nome_peer, uri)

    print(f"[{nome_peer}] URI registrada: {uri}")
    print(f"[{nome_peer}] Rodando...")

    # Monitorar o tracker
    threading.Thread(target=monitorar_tracker, args=(peer,), daemon=True).start()
    # Monitorar os arquivos
    threading.Thread(target=monitorar_arquivos, args=(peer, pasta_arquivos), daemon=True).start()
    
    daemon.requestLoop()

def monitorar_tracker(peer):
    while True:
        time.sleep(random.uniform(0.15, 0.3))  # intervalo aleatório
        if not peer.recebeu_heartbeat:
            print(f"[{peer.nome}] Tracker ausente. Iniciando eleição...")
            eleger_tracker(peer)
        elif not peer.e_tracker:
            peer.recebeu_heartbeat = False

def monitorar_arquivos(peer, pasta_arquivos):
    arquivos_anteriores = set(peer.arquivos)
    while True:
        time.sleep(1)
        arquivos_atualizados = set(os.listdir(pasta_arquivos))
        novos_arquivos = arquivos_atualizados - arquivos_anteriores
        if novos_arquivos:
            for novo_arquivo in novos_arquivos:
                peer.adicionar_arquivo(novo_arquivo)
                print(f"[{peer.nome}] Novo arquivo detectado e adicionado: {novo_arquivo}")
            arquivos_anteriores = arquivos_atualizados

def eleger_tracker(peer):
    if peer.em_eleicao:
        return
    peer.em_eleicao = True
    try:
        ns = Pyro5.api.locate_ns()

        tempo_limite = time.time() - 0.5
        peers_disponiveis = []

        # Tenta filtrar peers que respondem ao heartbeat
        for nome, uri in ns.list().items():
            if nome.startswith("peer"):
                try:
                    proxy = Pyro5.api.Proxy(uri)
                    proxy._pyroTimeout = 0.2
                    proxy.heartbeat()
                    peers_disponiveis.append(nome)
                except:
                    continue

        votos = 1  # vota em si mesmo
        epoca_nova = peer.epoch + 1
        for outro_nome in peers_disponiveis:
            if outro_nome == peer.nome:
                continue
            try:
                proxy = Pyro5.api.Proxy(ns.lookup(outro_nome))
                if proxy.votar(peer.nome, epoca_nova):
                    votos += 1
            except:
                continue

        if votos >= (len(peers_disponiveis) + 1) // 2:
            uri = ns.lookup(peer.nome)

            # Remover trackers antigos
            for name in ns.list().keys():
                if name.startswith("Tracker_Epoca_"):
                    try:
                        ns.remove(name)
                    except:
                        pass

            nome_tracker = f"Tracker_Epoca_{epoca_nova}"
            ns.register(nome_tracker, uri)

            peer.e_tracker = True
            peer.epoch = epoca_nova
            print(f"[{peer.nome}] Foi eleito como novo TRACKER ({nome_tracker}) com {votos} votos")

            threading.Thread(target=enviar_heartbeat, args=(peer,), daemon=True).start()
        else:
            print(f"[{peer.nome}] Eleição falhou ({votos} votos)")
    finally:
        peer.em_eleicao = False

def enviar_heartbeat(peer):
    ns = Pyro5.api.locate_ns()
    while peer.e_tracker:
        time.sleep(0.1)

        # Remove peers inativos (>5s)
        agora = time.time()
        for peer_name in list(peer.vivos):
            if agora - peer.vivos[peer_name] > 5:
                del peer.vivos[peer_name]

        for nome, uri in ns.list().items():
            if nome.startswith("peer"):
                try:
                    proxy = Pyro5.api.Proxy(uri)
                    proxy.heartbeat()
                except:
                    continue

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python peer.py nome_peer")
    else:
        iniciar_peer(sys.argv[1])
