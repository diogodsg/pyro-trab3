import Pyro5.api
import threading
import time

# 1) Criar 2 classes
@Pyro5.api.expose
class ClasseA:
    def mensagem(self):
        return "Olá do objeto A"

@Pyro5.api.expose
class ClasseB:
    def mensagem(self):
        return "Olá do objeto B"

# Função para executar o serviço de nomes em thread separada
def iniciar_servico_nomes():
    Pyro5.nameserver.start_ns_loop()

def main():
    # 2) Instanciar o Daemon
    daemon = Pyro5.api.Daemon()

    # 3) Registrar objeto pyro no daemon
    objeto_a = ClasseA()
    objeto_b = ClasseB()
    uri_a = daemon.register(objeto_a)
    uri_b = daemon.register(objeto_b)

    # 4) Executar o serviço de nomes
    thread_ns = threading.Thread(target=iniciar_servico_nomes, daemon=True)
    thread_ns.start()
    time.sleep(1)  # Esperar o serviço de nomes iniciar

    # 5) Registrar URI no serviço de nomes
    ns = Pyro5.api.locate_ns()
    ns.register("objeto.a", uri_a)
    ns.register("objeto.b", uri_b)

    print("Objetos registrados:")
    print("URI A:", uri_a)
    print("URI B:", uri_b)

    # 6) Consultar URI do outro objeto no serviço de nomes
    uri_a_consultado = ns.lookup("objeto.a")
    uri_b_consultado = ns.lookup("objeto.b")
    print("URI consultado A:", uri_a_consultado)
    print("URI consultado B:", uri_b_consultado)

    print("Servidor rodando. Pressione Ctrl+C para sair.")
    daemon.requestLoop()

if __name__ == "__main__":
    main()
