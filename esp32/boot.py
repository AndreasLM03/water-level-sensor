import network
import time
import machine

WIFI_SSID = "DEIN_WLAN"
WIFI_PASSWORD = "DEIN_WLAN_PASSWORT"

# Ein Watchdog schon hier schuetzt auch die WLAN-Verbindungsphase beim Boot.
# main.py legt keinen zweiten WDT an, sondern nutzt dieses globale Objekt weiter,
# weil boot.py und main.py auf dem ESP32 denselben Namensraum teilen.
wdt = machine.WDT(timeout=60000)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while not wlan.isconnected():
        wdt.feed()
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except OSError:
            pass
        for _ in range(20):
            wdt.feed()
            if wlan.isconnected():
                break
            time.sleep(1)
    return wlan


connect_wifi()
