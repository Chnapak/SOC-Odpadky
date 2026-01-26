import json
import time
import requests

ESP_IP = "192.168.4.1" # Neměnit
PING_URL = f"http://{ESP_IP}/ping" # Testování spojení s Arduinem
DATA_URL = f"http://{ESP_IP}/data" # Posílání kolik má Arduino udělat kroků s motorem. 

def main():
    try:
        # 1) Ping
        r = requests.get(PING_URL, timeout=2)
        r.raise_for_status()
        print("Ping OK:", r.text) # pong = dobře.

        # 2) Poslat data v JSON
        # Můžeš poslat "angle" nebo "steps". Arduino si s tím poradí. Angle je v °
        payload = {"steps": 1000} # Zpráva k odeslání
        r = requests.post(DATA_URL, json=payload, timeout=2) # Poslání zprávy
        r.raise_for_status() # Hodí vyjímku, když není OK. :(
        print("POST /data OK:", r.text)

        # Kroky nesmí jít rovnou za sebou. Arduino je přechytralý a vykonává kroky, co nejrychleji.
        # Např. pokud by přišel předchozí příkaz na 8888 kroků a hned potom -1000, tak udělá jenom 7888 kroků nikoliv 9888.
        # Proto se hodí sleep.
        time.sleep(10)

        # Další příklad poslání zprávy
        payload = {"steps": -1000}
        r = requests.post(DATA_URL, json=payload, timeout=2)
        r.raise_for_status() 
        print("POST /data OK:", r.text)

        # Papír 0°
        # Plast 72°
        # Kov 144°
        # Sklo 216°
        # Směs 288°

    except requests.exceptions.RequestException as e:
        # Popíše chybu, když program selže.
        # Např. Arduino je vyplé, nejsi na wifi, špatně poslaná žádost.
        print("Request failed:", e)

if __name__ == "__main__":
    main()
