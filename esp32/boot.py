import network
import time
import machine
import config

# Ein Watchdog schon hier schuetzt auch die WLAN-Verbindungsphase beim Boot.
# main.py legt keinen zweiten WDT an, sondern nutzt dieses globale Objekt weiter,
# weil boot.py und main.py auf dem ESP32 denselben Namensraum teilen.
# 120s statt 60s, damit ein einzelner haengender Verbindungsversuch (z.B. eine
# ungueltige/nicht erreichbare MQTT_BROKER-Adresse) Zeit zum saubern Fehlschlagen
# hat, bevor der Wachhund eingreift.
wdt = machine.WDT(timeout=120000)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    # Erst aus- und wieder einschalten erzwingt einen echten Reset des WLAN-Treibers.
    # Wichtig nach einem Soft-Reboot (z.B. Thonnys "Restart"): der setzt nur die
    # Python-Ebene zurueck, nicht den Funkchip darunter - der kann sonst in einem
    # alten/haengenden Zustand von vor dem Neustart weiterlaufen.
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    while not wlan.isconnected():
        wdt.feed()
        # Vor jedem Versuch sauber trennen - ein erneutes connect() auf einer
        # Schnittstelle, die noch mit dem letzten Versuch beschaeftigt ist, kann
        # den WLAN-Treiber in einen Zustand bringen, der auf C-Ebene haengt und
        # sich per Python-seitigem feed() nicht mehr retten laesst.
        try:
            wlan.disconnect()
        except OSError:
            pass
        try:
            wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        except OSError:
            pass
        for _ in range(20):
            wdt.feed()
            if wlan.isconnected():
                break
            time.sleep(1)
    return wlan


connect_wifi()
