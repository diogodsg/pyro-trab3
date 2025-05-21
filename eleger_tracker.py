import re
import Pyro5.api
import math
class ElegerTracker:

            
    def eleger(self, peer):
        print(f"[{peer.nome}] Eleger tracker", peer.epoch)

        if peer.em_eleicao:
            return
        
        # Se o peer já é tracker, não precisa eleger
        peer.em_eleicao = True
        self.epoch = peer.epoch
        self.votos = 1  # vota em si mesmo
        self.peer = peer

        try:
            self.ns = Pyro5.api.locate_ns()

            self.peers_disponiveis = self.peers_disponiveis()
            self.votos = self.coletar_votos()

            print(f"[{peer.nome}] Votos coletados: {self.votos} de {len(self.peers_disponiveis)} peers disponíveis")
            print( math.ceil((len(self.peers_disponiveis)) / 2))
            if self.votos >= math.ceil((len(self.peers_disponiveis) + 1) / 2):
                self.cleanup_old_trackers()
                uri = self.ns.lookup(peer.nome)

                nome_tracker = f"Tracker_Epoca_{self.epoch}"
                self.ns.register(nome_tracker, uri)

                peer.e_tracker = True
                peer.epoch = self.epoch
                print(f"[{peer.nome}] Foi eleito como novo TRACKER ({nome_tracker}) com {self.votos} votos")
                return True
            
            else:
                return False
        finally:
            peer.em_eleicao = False

    def peers_disponiveis(self):
        ns = Pyro5.api.locate_ns()
        peers_disponiveis = []
        for nome, uri in ns.list().items():
            if nome.startswith("peer"):
                try:
                    proxy = Pyro5.api.Proxy(uri)
                    proxy._pyroTimeout = 0.2
                    proxy.is_alive()
                    peers_disponiveis.append(nome)
                except Pyro5.errors.CommunicationError as e:
                    continue
        return peers_disponiveis

    def coletar_votos(self ):
        votos = self.votos
        for peer in self.peers_disponiveis:
            if peer == self.peer.nome:
                self.peer.votar(self.epoch)
                continue
            try:
                proxy = Pyro5.api.Proxy(self.ns.lookup(peer))
                if proxy.votar(self.epoch):
                    votos += 1
            except Pyro5.errors.CommunicationError as e:
                print(f"Erro ao coletar voto de {peer}: {e}")

        return votos
    
    def cleanup_old_trackers(self):
        try:
            ns = Pyro5.api.locate_ns()
            peers = list(ns.list().keys())

            tracker_names = [name for name in peers if re.match(r"^Tracker_Epoca_\d+$", name)]

            for name in tracker_names:
                try:
                    ns.remove(name)
                    print(f"Removido: {name}")
                except Exception as e:
                    print(f"Erro ao remover {name}: {e}")

        except Exception as e:
            print(f"Erro ao acessar o Name Server: {e}")