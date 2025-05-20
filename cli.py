import re
import argparse
import Pyro5.api
import base64

def get_tracker():
    try:
        ns = Pyro5.api.locate_ns()
        peers = list(ns.list().keys())
        tracker_nomes = [
            s for s in peers if re.match(r"^Tracker_Epoca_\d+$", s)
        ]

        if not tracker_nomes:
            print("Nenhum tracker encontrado.")
            return None

        # Encontra a string com o maior número ao final
        maior_tracker = max(tracker_nomes, key=lambda s: int(s.split("_")[-1]))
        uri = ns.lookup(maior_tracker)

        if not uri:
            print("URI do tracker não encontrada.")
            return None

        tracker = Pyro5.api.Proxy(uri)

        # Try to bind to check if it's alive
        tracker._pyroBind()
        return tracker

    except (Pyro5.errors.CommunicationError, Pyro5.errors.NamingError) as e:
        print(f"Erro ao conectar com o tracker: {e}")
        return None

def requisitar_arquivo(nome_arquivo):
    try:
        tracker = get_tracker()
        peers = tracker.localizar_arquivo(nome_arquivo)
    except Exception as e:
        print("Erro ao conectar com o tracker:", e)
        return

    if not peers:
        print(f"❌ Arquivo '{nome_arquivo}' não encontrado.")
        return
    print("Nós com arquivo")
    for i, peer in enumerate(peers):
        print(f"{i} - {peer}")

    index = int(input('De onde deseja baixar o arquivo?: '))
    peer_to_download = peers[index]
    uri = ns.lookup(peer_to_download)
    peer = Pyro5.api.Proxy(uri)
    conteudo = peer.baixar_arquivo(nome_arquivo)
    # Salva localmente
    with open(f"./downloads/{nome_arquivo}", "wb") as f:
        f.write(base64.b64decode(conteudo["data"]))
    print(f"✅ Arquivo '{nome_arquivo}' recebido de {uri}:\n")    
    

def main():
    parser = argparse.ArgumentParser(description="CLI para requisitar arquivos de uma rede P2P via Pyro5")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    # Comando: requisitar <nome_arquivo>
    parser_req = subparsers.add_parser("requisitar", help="Requisita um arquivo da rede P2P")
    parser_req.add_argument("arquivo", type=str, help="Nome do arquivo a ser requisitado")

    args = parser.parse_args()

    if args.comando == "requisitar":
        requisitar_arquivo(args.arquivo)

if __name__ == "__main__":
    main()
