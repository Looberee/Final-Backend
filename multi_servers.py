from multiprocessing import Process
import os

def start_server(server_script):
    os.system(f'python {server_script}')

if __name__ == "__main__":
    
    servers = ['admin_api.py', 'user_api.py', 'user_server.py', 'backup_user_server.py', 'pyppo_live.py', 'admin_server.py']
    
    processes = []

    for server_file in servers:
        p = Process(target=start_server, args=(server_file,))
        p.start()
        processes.append(p)

    for process in processes:
        process.join()