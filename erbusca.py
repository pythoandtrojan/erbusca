
#!/usr/bin/env python3
import urllib.request
import urllib.error
import socket
import sys
import json
import time
import argparse
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# [...] (o resto das constantes e funções permanecem iguais até a função check_username)

def check_username(username, selected_sites=None, quiet=False, 
                  timeout=10, max_workers=10, proxy=None,
                  print_all=False, no_save=False, txt_only=False, json_only=False):
    
    all_sites = load_sites()
    
    # Filtrar sites se especificado
    sites = {}
    if selected_sites:
        for site in selected_sites:
            if site in all_sites:
                sites[site] = all_sites[site]
            else:
                print(f"{AMARELO}[!] Site não encontrado: {site}{RESET}")
    else:
        sites = all_sites.copy()
    
    if not quiet:
        print(LOGO)
        print(f"{CIANO}[*] Verificando o nome de usuário: {username}{RESET}")
        print(f"{CIANO}[*] Sites a verificar: {len(sites)}{RESET}")
        print(f"{CIANO}[*] Threads: {max_workers}{RESET}")
        if proxy:
            print(f"{CIANO}[*] Usando proxy: {proxy}{RESET}")
        print()
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, site, data, username, timeout, proxy): site 
            for site, data in sites.items()
        }
        
        for future in as_completed(futures):
            site = futures[future]
            try:
                result = future.result()
                results[site] = result
                
                if not quiet or (print_all and result["exists"]):
                    if result["error"]:
                        print(f"{AMARELO}[?] {site}: {result['error']} ({result['time']:.2f}s){RESET}")
                    elif result["exists"]:
                        print(f"{VERDE}[+] {site}: Encontrado! ({result['time']:.2f}s){RESET}")
                        print(f"    {result['url']}\n")
                    elif print_all:
                        print(f"{VERMELHO}[-] {site}: Não encontrado ({result['time']:.2f}s){RESET}")
                        
            except Exception as e:
                print(f"{VERMELHO}[!] Erro ao verificar {site}: {str(e)}{RESET}")
    
    # Criar pasta de resultados se não existir
    results_dir = "resultados"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Gerar relatórios
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"resultado_{username}_{timestamp}"
    
    if not no_save:
        if not json_only:
            # Gerar relatório TXT
            txt_filename = os.path.join(results_dir, f"{base_filename}.txt")
            with open(txt_filename, "w", encoding="utf-8") as f:
                f.write(f"Resultado para: {username}\n")
                f.write(f"Data: {timestamp}\n")
                f.write(f"Total de sites: {len(sites)}\n")
                f.write("="*50 + "\n\n")
                
                for site, data in results.items():
                    if data["error"]:
                        f.write(f"[?] {site}: {data['error']} ({data['time']:.2f}s)\n")
                    elif data["exists"]:
                        f.write(f"[+] {site}: {data['url']} ({data['time']:.2f}s)\n")
                    else:
                        f.write(f"[-] {site}: Não encontrado ({data['time']:.2f}s)\n")
                
                if not quiet:
                    print(f"\n{CIANO}[*] Relatório TXT salvo em: {txt_filename}{RESET}")
        
        if not txt_only:
            # Gerar relatório JSON
            json_filename = os.path.join(results_dir, f"{base_filename}.json")
            report = {
                "username": username,
                "date": timestamp,
                "sites_checked": len(sites),
                "results": results
            }
            
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            if not quiet:
                print(f"{CIANO}[*] Relatório JSON salvo em: {json_filename}{RESET}")
    
    return results
