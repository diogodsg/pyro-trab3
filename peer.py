import Pyro5.api
import threading
import time
import os
import random
import socket
from eleger_tracker import ElegerTracker
from cli import get_tracker

class Peer:
    def __init__(self, nome: str, arquivos: list[str]):
        self.nome = nome
        self.uri =''
        self.arquivos = arquivos
        self.tracker_uri = None
        self.epoch = 0
        self.votou_na_epoca = set()
        self.e_tracker = False
        self.em_eleicao = False
        self.indice = {}
        self.pasta_arquivos = os.path.join("arquivos", nome)

    @Pyro5.api.expose
    def localizar_arquivo(self, arquivo: str):
        nos_com_arquivo = []
        for peer in self.indice.keys():
            if arquivo in self.indice[peer]:
                nos_com_arquivo.append(peer)
                continue
        return nos_com_arquivo
    
    @Pyro5.api.expose
    def receber_arquivos(self, nome_peer: str, arquivos: list[str]):
        print(f"Arquivos recebidos de [{nome_peer}]: {arquivos}")
        self.indice[nome_peer] = arquivos


    @Pyro5.api.expose
    def adicionar_arquivo(self, nome_arquivo):
        if nome_arquivo not in self.arquivos:
            self.arquivos.append(nome_arquivo)

            if self.e_tracker:
                print(f"[{self.nome}] Atualizando índice com novo arquivo: {nome_arquivo}")
                # aqui você pode atualizar um dicionário de índice local se quiser
            elif self.tracker_uri and self.tracker_uri != self.uri:
                try:
                    tracker = Pyro5.api.Proxy(self.tracker_uri)
                    tracker.receber_arquivos(self.nome, self.arquivos)
                    
                    print(f"[{self.nome}] Avisou o tracker sobre novo arquivo: {nome_arquivo}")
                except Exception as e:
                    print(f"[{self.nome}] Erro ao avisar o tracker: {e}")

    @Pyro5.api.expose
    def heartbeat(self, uri, epoch: int):
        if not self.tracker_uri:
            self.tracker_uri = uri 
            if self.tracker_uri != self.uri:
                tracker = Pyro5.api.Proxy(self.tracker_uri)
                tracker.receber_arquivos(self.nome, self.arquivos)
        if epoch >= self.epoch:
            self.epoch = epoch
  

    @Pyro5.api.expose
    def registrar_tracker(self, uri, epoch):
        self.tracker_uri = uri
        self.epoch = epoch
        print(f"[{self.nome}] Novo tracker registrado: {uri} (época {epoch})")

        proxy = Pyro5.api.Proxy(self.tracker_uri)
        proxy.receber_arquivos(self.nome, self.arquivos)


    @Pyro5.api.expose
    def baixar_arquivo(self, nome_arquivo):
        caminho = os.path.join(self.pasta_arquivos, nome_arquivo)
        print(caminho)
        if not os.path.exists(caminho):
            return f"Erro: arquivo '{nome_arquivo}' não encontrado."

        with open(caminho, "rb") as f:
            conteudo = f.read()
        
        return conteudo  # será enviado como bytes via Pyro
    
    @Pyro5.api.expose
    def is_alive(self):
        return True
    
    @Pyro5.api.expose
    def votar(self, epoca):
        if epoca not in self.votou_na_epoca:
            self.votou_na_epoca.add(epoca)
            return True
        return False

def avisar_resultado_eleicao(peer):
    ns = Pyro5.api.locate_ns()

    for nome, uri in ns.list().items():
        if nome.startswith("peer") and nome != peer.nome:
            try:
                proxy = Pyro5.api.Proxy(uri)
                proxy.registrar_tracker(peer.uri, peer.epoch)
            except:
                continue

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
    peer.uri = uri
    print(f"[{nome_peer}] URI registrada: {uri}")
    print(f"[{nome_peer}] Rodando...")

    # Monitorar o tracker
    threading.Thread(target=monitorar_tracker, args=(peer,), daemon=True).start()
    # Monitorar os arquivos
    threading.Thread(target=monitorar_arquivos, args=(peer, pasta_arquivos), daemon=True).start()
    
    daemon.requestLoop()

def monitorar_tracker(peer):
    if peer.e_tracker:
        return
    
    while True:
        time.sleep(random.uniform(0.15, 0.3))  # intervalo aleatório
        tracker = get_tracker()
        if not tracker:
            print(f"[{peer.nome}] Tracker ausente. Iniciando eleição...")
            eleito = False
            while not eleito:
                peer.epoch += 1
                peer.votou_na_epoca.add(peer.epoch)
                eleito = ElegerTracker().eleger(peer)
                if eleito:
                    threading.Thread(target=enviar_heartbeat, args=(peer,), daemon=True).start()
                    avisar_resultado_eleicao(peer=peer)
                    print(f"[{peer.nome}] Eleição concluída. Tracker registrado.")
                    break
            

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


def enviar_heartbeat(peer):
    ns = Pyro5.api.locate_ns()
    while peer.e_tracker:
        time.sleep(0.1)

        for nome, uri in ns.list().items():
            if nome.startswith("peer"):
                try:
                    proxy = Pyro5.api.Proxy(uri)
                    proxy.heartbeat(peer.uri, peer.epoch)
                except:
                    continue

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python peer.py nome_peer")
    else:
        iniciar_peer(sys.argv[1])
