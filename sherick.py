#!/usr/bin/env python3
import urllib.request
import urllib.error
import socket
import sys
import json
import time
import argparse
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cores ANSI para Termux
VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
AZUL = "\033[94m"
CIANO = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

# ASCII Art
LOGO = f"""
{CIANO}  ____  _               _      _    
 / ___|| |__   ___ _ __| | ___| | __
 \___ \| '_ \ / _ \ '__| |/ __| |/ /
  ___) | | | |  __/ |  | | (__|   < 
 |____/|_| |_|\___|_|  |_|\___|_|\_\\
 {RESET}{MAGENTA}Termux Edition{RESET}
"""

# User-Agents rotativos
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 10; SM-A505FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
]

def load_sites(filename="sites.json"):
    """Carrega os sites do arquivo JSON com estrutura categorizada"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            flat_sites = {}
            
            # Processa estrutura categorizada
            for category, sites in data.items():
                if isinstance(sites, dict):
                    for site_name, site_data in sites.items():
                        site_data['category'] = category  # Adiciona categoria
                        flat_sites[site_name] = site_data
            
            return flat_sites
    except Exception as e:
        print(f"{VERMELHO}[!] Erro ao carregar sites: {str(e)}{RESET}")
        return get_default_sites()

def get_default_sites():
    """Fallback com sites padrão"""
    return {
        "Instagram": {
            "url": "https://www.instagram.com/{}/",
            "category": "social",
            "check_methods": [
                {"type": "status_code", "expect": 200},
                {"type": "redirect", "pattern": "accounts/login"},
                {"type": "content", "pattern": "Sorry, this page isn't available"},
                {"type": "api", "url": "https://www.instagram.com/api/v1/users/web_profile_info/?username={}"}
            ]
        },
        "GitHub": {
            "url": "https://github.com/{}",
            "category": "code",
            "check_methods": [
                {"type": "status_code", "expect": 200},
                {"type": "content", "pattern": "This is not the web page you are looking for"}
            ]
        }
    }

def check_site(site, data, username, timeout, proxy=None):
    """Verifica um único site com múltiplos métodos"""
    result = {
        "site": site,
        "url": data["url"].format(username),
        "category": data.get("category", "unknown"),
        "exists": False,
        "error": None,
        "time": 0,
        "method_used": None
    }
    
    # Tenta cada método de verificação
    for method in data.get("check_methods", []):
        try:
            start_time = time.time()
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'DNT': '1'
            }
            
            # Mostra status em tempo real
            print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET}", end='\r', flush=True)
            
            if method["type"] == "api":
                api_url = method["url"].format(username)
                req = urllib.request.Request(api_url, headers=headers)
            else:
                req = urllib.request.Request(result["url"], headers=headers, method='HEAD' if method.get("use_head", False) else 'GET')
            
            if proxy:
                req.set_proxy(proxy, "http")
            
            socket.setdefaulttimeout(timeout)
            
            with urllib.request.urlopen(req) as response:
                elapsed = time.time() - start_time
                content = response.read().decode('utf-8', errors="ignore") if method["type"] in ["content", "api"] else ""
                status = response.getcode()
                
                if method["type"] == "status_code":
                    if status == method["expect"]:
                        result.update({
                            "exists": True,
                            "time": elapsed,
                            "method_used": "status_code"
                        })
                        print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET} {VERDE}✓ {elapsed:.2f}s{RESET}")
                        return result
                
                elif method["type"] == "redirect":
                    if method["pattern"] in response.geturl():
                        result.update({
                            "time": elapsed,
                            "method_used": "redirect"
                        })
                        print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET} {VERMELHO}✗ {elapsed:.2f}s{RESET}")
                        return result
                
                elif method["type"] == "content":
                    if method["pattern"].lower() in content.lower():
                        result.update({
                            "time": elapsed,
                            "method_used": "content"
                        })
                        print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET} {VERMELHO}✗ {elapsed:.2f}s{RESET}")
                        return result
                
                elif method["type"] == "api":
                    if '"user":null' not in content:
                        result.update({
                            "exists": True,
                            "time": elapsed,
                            "method_used": "api"
                        })
                        print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET} {VERDE}✓ {elapsed:.2f}s{RESET}")
                        return result
            
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_time
            result.update({
                "error": f"HTTP {e.code}",
                "time": elapsed,
                "method_used": method["type"]
            })
            continue
            
        except Exception as e:
            elapsed = time.time() - start_time
            result.update({
                "error": str(e),
                "time": elapsed,
                "method_used": method["type"]
            })
            continue
    
    # Se nenhum método confirmou a existência
    if result["error"] is None:
        result["error"] = "Not found by any method"
    print(f"{AZUL}[*] Checking {site.ljust(20)}{RESET} {VERMELHO}✗ {result['time']:.2f}s{RESET}")
    return result

def check_username(username, selected_sites=None, quiet=False, 
                  timeout=10, max_workers=10, proxy=None,
                  print_all=False, no_save=False, txt_only=False, json_only=False):
    
    all_sites = load_sites()
    sites = {}
    
    # Filtra sites por seleção ou categoria
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
        print(f"{CIANO}[*] Verificando usuário: {username}{RESET}")
        print(f"{CIANO}[*] Sites: {len(sites)} | Threads: {max_workers} | Timeout: {timeout}s{RESET}")
        if proxy:
            print(f"{CIANO}[*] Usando proxy: {proxy}{RESET}")
        print(f"{AZUL}────────────────────────────────────────────{RESET}")
    
    results = {}
    stats = {"found": 0, "not_found": 0, "errors": 0}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_site, site, data, username, timeout, proxy): site 
            for site, data in sites.items()
        }
        
        for future in as_completed(futures):
            site = futures[future]
            try:
                result = future.result()
                results[site] = result
                
                if result["exists"]:
                    stats["found"] += 1
                elif result["error"]:
                    stats["errors"] += 1
                else:
                    stats["not_found"] += 1
                    
            except Exception as e:
                print(f"{VERMELHO}[!] Erro verificando {site}: {str(e)}{RESET}")
                stats["errors"] += 1
    
    # Resumo colorido
    if not quiet:
        print(f"\n{CIANO}─────────────── RESUMO ───────────────{RESET}")
        print(f"{VERDE}✓ Encontrados: {stats['found']}{RESET}")
        print(f"{VERMELHO}✗ Não encontrados: {stats['not_found']}{RESET}")
        print(f"{AMARELO}⚠️ Erros: {stats['errors']}{RESET}")
        print(f"{CIANO}────────────────────────────────────{RESET}\n")
    
    # Geração de relatórios
    if not no_save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"results/result_{username}_{timestamp}"
        
        if not os.path.exists("results"):
            os.makedirs("results")
        
        if not json_only:
            # Relatório TXT organizado por categoria
            with open(f"{base_filename}.txt", "w", encoding="utf-8") as f:
                f.write(f"Resultado para: {username}\n")
                f.write(f"Data: {timestamp}\n")
                f.write(f"Total: {len(sites)} | Encontrados: {stats['found']} | Não encontrados: {stats['not_found']} | Erros: {stats['errors']}\n")
                f.write("="*50 + "\n\n")
                
                # Agrupa por categoria
                by_category = {}
                for site, data in results.items():
                    category = data.get("category", "Outros")
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append((site, data))
                
                # Escreve por categoria
                for category, sites in sorted(by_category.items()):
                    f.write(f"\n[{category.upper()}]\n")
                    for site, data in sorted(sites, key=lambda x: x[0]):
                        status = "✓" if data["exists"] else "✗"
                        color = VERDE if data["exists"] else VERMELHO if not data["error"] else AMARELO
                        f.write(f"{status} {site}: {data['url']} ({data['time']:.2f}s)\n")
                        if data["error"]:
                            f.write(f"   ! ERRO: {data['error']}\n")
        
        if not txt_only:
            # Relatório JSON completo
            with open(f"{base_filename}.json", "w", encoding="utf-8") as f:
                json.dump({
                    "username": username,
                    "date": timestamp,
                    "stats": stats,
                    "results": results
                }, f, indent=2, ensure_ascii=False)
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Busca de usuários em redes sociais - Termux Edition",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("usernames", nargs="+", help="Nomes de usuário para verificar")
    parser.add_argument("-s", "--sites", nargs="+", help="Sites específicos para verificar")
    parser.add_argument("-c", "--category", help="Filtrar por categoria (social, code, etc.)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Modo silencioso (apenas resultados)")
    parser.add_argument("-a", "--print-all", action="store_true", help="Mostrar todos os resultados")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout em segundos (padrão: 10)")
    parser.add_argument("-w", "--workers", type=int, default=10, help="Número de threads (padrão: 10)")
    parser.add_argument("-p", "--proxy", help="Usar proxy (ex: socks5://127.0.0.1:9050)")
    parser.add_argument("--no-save", action="store_true", help="Não salvar relatórios")
    parser.add_argument("--txt-only", action="store_true", help="Salvar apenas relatório TXT")
    parser.add_argument("--json-only", action="store_true", help="Salvar apenas relatório JSON")
    
    args = parser.parse_args()
    
    for username in args.usernames:
        check_username(
            username=username,
            selected_sites=args.sites,
            quiet=args.quiet,
            timeout=args.timeout,
            max_workers=args.workers,
            proxy=args.proxy,
            print_all=args.print_all,
            no_save=args.no_save,
            txt_only=args.txt_only,
            json_only=args.json_only
        )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{VERMELHO}[!] Busca interrompida pelo usuário{RESET}")
        sys.exit(1)
