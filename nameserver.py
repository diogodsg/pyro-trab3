# servidor_nomes.py
from Pyro5.nameserver import start_ns_loop

if __name__ == "__main__":
    print("Iniciando o servidor de nomes Pyro5...")
    start_ns_loop()
