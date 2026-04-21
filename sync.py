#!/usr/bin/env python3
"""
Centro Oeste Implementos - Utilitário de Sincronização
Uso:
  python sync.py backup           # Baixa proposals.json do GitHub para local
  python sync.py restore          # Envia backup local para o GitHub
  python sync.py status           # Mostra quantas propostas estão no GitHub
  python sync.py export <arquivo> # Exporta propostas para JSON formatado
"""

import sys
import json
import base64
import os
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Instale as dependências: pip install -r requirements.txt")
    sys.exit(1)

# ── Configuração ─────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / ".gh_config.json"
DATA_FILE   = Path(__file__).parent / "backup" / "proposals.json"

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    token = os.environ.get("GH_TOKEN", "")
    owner = os.environ.get("GH_OWNER", "")
    repo  = os.environ.get("GH_REPO",  "")
    if token and owner and repo:
        return {"token": token, "owner": owner, "repo": repo}
    print("Configure o GitHub primeiro:")
    token = input("  Token (ghp_...): ").strip()
    owner = input("  Usuário/Org:     ").strip()
    repo  = input("  Repositório:     ").strip()
    cfg = {"token": token, "owner": owner, "repo": repo}
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Configuração salva em {CONFIG_FILE}")
    return cfg

def github_headers(cfg):
    return {
        "Authorization": f"token {cfg['token']}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

def gh_url(cfg):
    return f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/data/proposals.json"

# ── Operações ─────────────────────────────────────────────────────────────────
def cmd_backup(cfg):
    print("Baixando dados do GitHub...")
    r = requests.get(gh_url(cfg), headers=github_headers(cfg))
    if r.status_code == 404:
        print("Arquivo não encontrado no GitHub ainda (nenhuma proposta salva).")
        return
    r.raise_for_status()
    data = r.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    DATA_FILE.parent.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = DATA_FILE.parent / f"proposals_{ts}.json"
    out.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    DATA_FILE.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(content.get("proposals", []))
    print(f"Backup salvo: {out}  ({n} propostas)")

def cmd_restore(cfg):
    if not DATA_FILE.exists():
        print(f"Arquivo local não encontrado: {DATA_FILE}")
        print("Execute primeiro: python sync.py backup")
        return
    content = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    encoded = base64.b64encode(
        json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    # Obter SHA atual (necessário para update)
    sha = None
    r = requests.get(gh_url(cfg), headers=github_headers(cfg))
    if r.status_code == 200:
        sha = r.json()["sha"]

    body = {
        "message": f"restore: {datetime.now().isoformat()}",
        "content": encoded,
    }
    if sha:
        body["sha"] = sha

    r = requests.put(gh_url(cfg), headers=github_headers(cfg), json=body)
    r.raise_for_status()
    n = len(content.get("proposals", []))
    print(f"Restaurado com sucesso! ({n} propostas enviadas ao GitHub)")

def cmd_status(cfg):
    print("Verificando GitHub...")
    r = requests.get(gh_url(cfg), headers=github_headers(cfg))
    if r.status_code == 404:
        print("Sem dados no GitHub ainda.")
        return
    r.raise_for_status()
    data = r.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    proposals = content.get("proposals", [])
    sellers   = content.get("sellers", [])
    print(f"Repositório : {cfg['owner']}/{cfg['repo']}")
    print(f"Propostas   : {len(proposals)}")
    print(f"Vendedores  : {len(sellers)}")
    if proposals:
        last = proposals[0]
        print(f"Última      : {last.get('num','-')}  |  {last.get('clientName','-')}  |  {last.get('status','-')}")

def cmd_export(cfg, filename):
    print("Baixando dados do GitHub para exportar...")
    r = requests.get(gh_url(cfg), headers=github_headers(cfg))
    r.raise_for_status()
    data = r.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    Path(filename).write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exportado para: {filename}  ({len(content.get('proposals',[]))} propostas)")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cfg = load_config()
    cmd = args[0].lower()

    if cmd == "backup":
        cmd_backup(cfg)
    elif cmd == "restore":
        cmd_restore(cfg)
    elif cmd == "status":
        cmd_status(cfg)
    elif cmd == "export":
        filename = args[1] if len(args) > 1 else f"export_{datetime.now().strftime('%Y%m%d')}.json"
        cmd_export(cfg, filename)
    else:
        print(f"Comando desconhecido: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
