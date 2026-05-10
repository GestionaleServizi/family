#!/usr/bin/env python3
"""
FamilyControl Agent Android (Termux) - MODALITÀ ON-DEMAND
NON riempie il database - Invia SOLO dati richiesti via comandi
"""

import os
import json
import time
import socket
import subprocess
from datetime import datetime
import requests

# Configurazione Supabase
SUPABASE_URL = 'https://rclarbbasnnwmwhpoenn.supabase.co'
SUPABASE_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6InNlcnZpY2Vfcm9sZSIsImlzcyI6InN1cGFiYXNlIiwicmVmIjoicmNsYXJiYmFzbm53bXdocG9lbm4iLCJyb2xlIjoic2VydmljZV9yb2xlIiwiaWF0IjoxNzc4MjM3ODk2LCJleHAiOjIwOTM4MTM4OTZ9.JqC7WX6-HbWk4NlJoDmSa46XGn74bmfO3dxwVgOv6hU'

# ID dispositivo
try:
    DEVICE_ID = subprocess.check_output(['getprop', 'ro.serialno']).decode().strip()
except:
    DEVICE_ID = f"android-termux"

DEVICE_NAME = f"Smartphone Android"
DEVICE_TYPE = "android"

# Headers per Supabase
HEADERS = {
    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
    'Content-Type': 'application/json',
    'apikey': SUPABASE_SERVICE_KEY
}

class FamilyControlAgentAndroid:
    def __init__(self):
        self.device_id = DEVICE_ID
        self.running = True
        self.commands_executed = 0
        
        print("""
╔════════════════════════════════════════════════════════════╗
║  FamilyControl Android - MODALITÀ ON-DEMAND               ║
║  ✅ NON riempie il database                               ║
║  ✅ Controlla comandi ogni 5 secondi                      ║
║  ✅ Invia SOLO dati richiesti                             ║
╚════════════════════════════════════════════════════════════╝
        """)

    def register_device(self):
        """Registra il dispositivo su Supabase"""
        try:
            response = requests.get(
                f'{SUPABASE_URL}/rest/v1/devices?id=eq.{self.device_id}',
                headers=HEADERS,
                timeout=10
            )
            
            if response.status_code == 200 and len(response.json()) == 0:
                device_data = {
                    'id': self.device_id,
                    'name': DEVICE_NAME,
                    'device_type': DEVICE_TYPE,
                    'status': 'online',
                    'last_seen': datetime.now().isoformat()
                }
                
                response = requests.post(
                    f'{SUPABASE_URL}/rest/v1/devices',
                    headers=HEADERS,
                    json=device_data,
                    timeout=10
                )
                print(f"✅ Dispositivo registrato: {DEVICE_NAME}")
            else:
                self.update_device_status('online')
                print(f"✅ Dispositivo già registrato: {DEVICE_NAME}")
                
        except Exception as e:
            print(f"❌ Errore registrazione: {e}")

    def update_device_status(self, status):
        """Aggiorna solo lo status"""
        try:
            requests.patch(
                f'{SUPABASE_URL}/rest/v1/devices?id=eq.{self.device_id}',
                headers=HEADERS,
                json={'status': status, 'last_seen': datetime.now().isoformat()},
                timeout=5
            )
        except Exception as e:
            print(f"⚠️ Errore status: {e}")

    def get_device_info(self):
        """Ottiene info dispositivo"""
        try:
            brand = subprocess.check_output(['getprop', 'ro.product.brand']).decode().strip()
            model = subprocess.check_output(['getprop', 'ro.product.model']).decode().strip()
            android_version = subprocess.check_output(['getprop', 'ro.build.version.release']).decode().strip()
            
            return {
                'device_name': f"{brand} {model}",
                'android_version': android_version,
                'timestamp': datetime.now().isoformat()
            }
        except:
            return {'error': 'Impossibile leggere info dispositivo'}

    def get_installed_apps(self):
        """Ottiene lista app installate"""
        try:
            result = subprocess.check_output(['pm', 'list', 'packages']).decode()
            apps = [line.replace('package:', '') for line in result.split('\n') if 'package:' in line]
            return apps[:30]  # Prime 30 app
        except:
            return []

    def get_running_apps(self):
        """Ottiene app in esecuzione"""
        try:
            result = subprocess.check_output(['ps']).decode()
            lines = result.split('\n')[1:]  # Salta header
            apps = []
            for line in lines[:20]:
                parts = line.split()
                if len(parts) > 1:
                    app_name = parts[-1]
                    apps.append(app_name)
            return apps
        except:
            return []

    def get_battery_info(self):
        """Ottiene info batteria"""
        try:
            result = subprocess.check_output(['dumpsys', 'battery']).decode()
            battery_info = {}
            for line in result.split('\n'):
                if 'level:' in line:
                    battery_info['level'] = line.split('level:')[1].strip()
                if 'temperature:' in line:
                    battery_info['temperature'] = line.split('temperature:')[1].strip()
                if 'status:' in line and 'status:' in line:
                    battery_info['status'] = line.split('status:')[1].strip()
            return battery_info
        except:
            return {}

    def get_screen_time(self):
        """Calcola tempo schermo (approssimativo)"""
        try:
            result = subprocess.check_output(['dumpsys', 'usagestats']).decode()
            # Parsing semplice
            return {'screen_on_time': 'Unknown'}
        except:
            return {}

    def get_contacts(self):
        """Ottiene numero contatti (info generica)"""
        try:
            # In Termux non possiamo accedere direttamente ai contatti
            # Restituiamo un numero fittizio
            return {'total_contacts': 'N/A', 'note': 'Accesso contatti limitato in Termux'}
        except:
            return {}

    def get_whatsapp_info(self):
        """Controlla se WhatsApp è installato"""
        try:
            result = subprocess.check_output(['pm', 'list', 'packages'], stderr=subprocess.DEVNULL).decode()
            if 'com.whatsapp' in result:
                return {'whatsapp_installed': True, 'status': 'Installato'}
            else:
                return {'whatsapp_installed': False, 'status': 'Non installato'}
        except:
            return {'error': 'Impossibile verificare'}

    def get_location(self):
        """Ottiene posizione (richiede servizi di localizzazione)"""
        try:
            # In Termux è difficile accedere alla localizzazione
            # Restituiamo un messaggio informativo
            return {
                'location': 'Non disponibile in Termux',
                'note': 'Richiede accesso a servizi GPS',
                'status': 'Location services disabled'
            }
        except:
            return {'error': 'Impossibile ottenere posizione'}

    def send_data_on_demand(self, data_type, data_content):
        """Invia dati on-demand a Supabase"""
        try:
            payload = {
                'device_id': self.device_id,
                'device_type': DEVICE_TYPE,
                'created_at': datetime.now().isoformat()
            }
            
            payload[data_type] = data_content
            
            response = requests.post(
                f'{SUPABASE_URL}/rest/v1/device_data',
                headers=HEADERS,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ {data_type} inviato a Supabase")
                return True
            else:
                print(f"❌ Errore invio {data_type}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Errore invio: {e}")
            return False

    def check_commands(self):
        """Controlla comandi pendenti"""
        try:
            response = requests.get(
                f'{SUPABASE_URL}/rest/v1/commands?device_id=eq.{self.device_id}&status=eq.pending',
                headers=HEADERS,
                timeout=10
            )
            
            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    self.execute_command(cmd)
                    
        except Exception as e:
            print(f"⚠️ Errore lettura comandi: {e}")

    def execute_command(self, cmd):
        """Esegue comandi on-demand"""
        try:
            command = cmd['command']
            self.commands_executed += 1
            
            print(f"\n📡 Comando ricevuto: {command}")
            print(f"   (Totale comandi: {self.commands_executed})")
            
            if command == 'get_device_info':
                info = self.get_device_info()
                self.send_data_on_demand('device_info', info)
                
            elif command == 'get_apps':
                apps = self.get_running_apps()
                self.send_data_on_demand('open_apps', apps)
                
            elif command == 'get_battery':
                battery = self.get_battery_info()
                self.send_data_on_demand('battery_info', battery)
                
            elif command == 'get_contacts':
                contacts = self.get_contacts()
                self.send_data_on_demand('contacts', contacts)
                
            elif command == 'get_whatsapp':
                whatsapp = self.get_whatsapp_info()
                self.send_data_on_demand('whatsapp_status', whatsapp)
                
            elif command == 'get_location':
                location = self.get_location()
                self.send_data_on_demand('location', location)
                
            elif command == 'get_screen_time':
                screen = self.get_screen_time()
                self.send_data_on_demand('screen_time', screen)
                
            elif command == 'get_installed_apps':
                apps = self.get_installed_apps()
                self.send_data_on_demand('installed_apps', apps)
            
            # Marca comando come completato
            self.mark_command_done(cmd['id'])
            
        except Exception as e:
            print(f"❌ Errore esecuzione comando: {e}")

    def mark_command_done(self, command_id):
        """Marca comando come completato"""
        try:
            requests.patch(
                f'{SUPABASE_URL}/rest/v1/commands?id=eq.{command_id}',
                headers=HEADERS,
                json={'status': 'completed'},
                timeout=5
            )
        except Exception as e:
            print(f"⚠️ Errore marking comando: {e}")

    def run_loop(self):
        """Loop principale - MODALITÀ ON-DEMAND"""
        print(f"🚀 FamilyControl Android Agent avviato")
        print(f"📡 Modalità ON-DEMAND - Non invia dati automaticamente")
        print(f"⏰ Controlla comandi ogni 5 secondi")
        print(f"💾 Database: PROTETTO da spam!\n")
        
        self.register_device()
        
        while self.running:
            try:
                # ⭐ SOLO controlla comandi, NON invia dati
                self.check_commands()
                
                # Aggiorna status minimo
                self.update_device_status('online')
                
                # Aspetta prima di controllare di nuovo
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\n⏹️ Agent fermato")
                print(f"📊 Comandi eseguiti: {self.commands_executed}")
                self.running = False
                self.update_device_status('offline')
            except Exception as e:
                print(f"❌ Errore loop: {e}")
                time.sleep(10)

if __name__ == '__main__':
    agent = FamilyControlAgentAndroid()
    agent.run_loop()
