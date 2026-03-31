import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image, ImageOps  # Install pillow instead of PIL
import numpy as np
import cv2 as cv
import json
import time
import requests

ESP_IP = "192.168.4.1" # Neměnit
PING_URL = f"http://{ESP_IP}/ping" # Testování spojení s Arduinem
DATA_URL = f"http://{ESP_IP}/data" # Posílání kolik má Arduino udělat kroků s motorem.
NUMBER_OF_TYPES_TRASH = 5
 
def main():
    # Config
    cam = cv.VideoCapture(0)
    # Nepoužívat vědecký zapís čísel v této knihovně. Jde o nastavení, které musí být na začátku spuštění programu.
    # Např. 167 = 1.67-E2 ve vědeckém zápisu
    np.set_printoptions(suppress=True) 

    # Načíst model ze souboru.
    model = load_model("keras_model.h5", compile=False)

    # Načíst názvy skupin (skupiny odpadků: plast, papír, kov atd.)
    class_names = open("labels.txt", "r").readlines()

    # Připraví správný tvar array, který má být vstupem pro AI model.
    # Délka arraye je počet fotek, který určuje první číslo arraye.
    # (počet fotek, počet pixelů do šířky, počet pixelů do výšky, počet hodnot (R,G,B)) =
    # (1, 224, 224, 3)
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)

    size = (224, 224)

    while True:
        # Vyfotit jediný snímek
        # bool ret = vrátil jsi vůbec něco?
        # frame = snímek
        ret, frame = cam.read()

        if ret:
            cv.imwrite("captured_image.png", frame) # Uložit fotku
        else:
            print("Failed to capture image.") # ret = false, nemám fotku.
            break

        
        # Získá si data z obrázku
        image = Image.open("captured_image.png").convert("RGB")

        # Změní velikost obrázku na alespoň 224x224, ale ořezáním ze středu, nikoliv compresí.
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)

        # Převede obrázek do arraye správného tvaru.
        image_array = np.asarray(image)

        # Normalizuje hodnoty na interval od -1 do 1 místo 0 až 255
        # <0;255> => <-1;1>
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1

        # Přidá obrázek do dat. Může mít více obrázků.
        data[0] = normalized_image_array


        prediction = model.predict(data) # Model předpoví 
        index = np.argmax(prediction)   # Najde nejlepší odhad
        class_name = class_names[index] # Najde název nejlepšího odhadu
        confidence_score = prediction[0][index] # Najde procentuální odhad modelu 

        # Print názvu a důvery
        print("Class:", class_name[2:], end="")
        print("Confidence Score:", confidence_score)
        angle = None
        type_of_waste = class_name[2:(len(class_name)-1)]
        print(type_of_waste)

        if confidence_score <= 0.5:
            angle = -60
            print("Model si neni jisty")
        else:
            match type_of_waste:
                case "Plast":
                    angle = 0 * (360/NUMBER_OF_TYPES_TRASH)
                case "Sklo":
                    angle = 1 * (360/NUMBER_OF_TYPES_TRASH)
                case "Papir":
                    angle = 2 * (360/NUMBER_OF_TYPES_TRASH)
                case "Kovy":
                    angle = 3 * (360/NUMBER_OF_TYPES_TRASH)
                case "Smesi": 
                    angle = 4 * (360/NUMBER_OF_TYPES_TRASH)

        if angle == None:
            print("nebyla prirazena validni skupina")
            break
        
        try:
            # 1) Poslat data v JSON
            # Můžeš poslat "angle" nebo "steps". Arduino si s tím poradí. Angle je v °
            payload = {"angle": angle} # Zpráva k odeslání
            r = requests.post(DATA_URL, json=payload, timeout=2) # Poslání zprávy
            r.raise_for_status() # Hodí vyjímku, když není OK. :(
            time.sleep(1)
            print("POST /data OK:", r.text)
            time.sleep(2.0)
            

        except requests.exceptions.RequestException as e:
            # Popíše chybu, když program selže.
            # Např. Arduino je vyplé, nejsi na wifi, špatně poslaná žádost.
            print("Request failed:", e)
            


if __name__ == "__main__":
    main()
