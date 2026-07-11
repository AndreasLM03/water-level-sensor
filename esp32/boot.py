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
    wlan.active(True)
    while not wlan.isconnected():
        wdt.feed()
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
