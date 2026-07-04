# Kopiere diese Datei zu config.py und trage dort deine echten Werte ein.
# config.py wird per .gitignore nie committet - diese Datei (das Beispiel) schon.

# --- WLAN ---
WIFI_SSID = "DEIN_WLAN"
WIFI_PASSWORD = "DEIN_WLAN_PASSWORT"

# --- MQTT ---
MQTT_BROKER = "192.168.x.x"
MQTT_USER = "esp32"
MQTT_PASSWORD = "CHANGE_ME"
MQTT_CLIENT_ID = "zisterne-esp32"

# --- Kalibrierung: Werte aus der Nasskalibrierung (siehe README) ---
U0 = 0.41            # Volt am Shunt bei 0mm Fuellstand (Trockenmessung)
U1 = 1.22            # Volt am Shunt bei bekannter Eintauchtiefe
H1_MM = 1000         # Eintauchtiefe in mm, mit der U1 gemessen wurde

H_OFFSET_MM = 80     # Sonde haengt so viel ueber dem Zisternenboden
MAX_LEVEL_MM = 1900  # Fuellhoehe bei voller Zisterne
TOTAL_LITERS = 5300  # Gesamtvolumen der Zisterne

# Schwellwert fuer die adaptive Messfrequenz - MUSS nach der Installation anhand
# der tatsaechlichen Rauschstreuung kalibriert werden (siehe README "Schwellwert ermitteln")
CHANGE_THRESHOLD_MM = 8

# --- Adaptive Messfrequenz ---
INTERVAL_LONG_S = 300    # Normalfall: alle 5 Minuten
INTERVAL_SHORT_S = 20    # bei starker Aenderung: alle 20s
STABLE_COUNT_TARGET = 5  # so viele ruhige Messungen in Folge, bevor zurueck auf INTERVAL_LONG_S
