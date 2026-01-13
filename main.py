import tensorflow as tf
from keras.models import load_model  # TensorFlow is required for Keras to work
from PIL import Image, ImageOps  # Install pillow instead of PIL
import numpy as np
import cv2 as cv

# Tohle je zkušební soubor na testování AI. Neměnil bych ho, ale spíš bych měnil pouze Arduino_connection.
# Je možné testovat na tvém zařízení.

# Připravit kameru (0 = zvolit základní kameru, 1/2/3/4... = další kamery)
cam = cv.VideoCapture(0)

# Vyfotit jediný snímek
# bool ret = vrátil jsi vůbec něco?
# frame = snímek
ret, frame = cam.read()

if ret:
    cv.imshow("Captured", frame) # Ukázat okno s fotkou    
    cv.imwrite("captured_image.png", frame) # Uložit fotku
    cv.waitKey(2000) # Počkat
    cv.destroyWindow("Captured") # Vypnout okno s fotkou       
else:
    print("Failed to capture image.") # ret = false, nemám fotku.

cam.release() # Kamera se musí vypnout!!!!

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

# Získá si data z obrázku
image = Image.open("captured_image.png").convert("RGB")

# Změní velikost obrázku na alespoň 224x224, ale ořezáním ze středu, nikoliv compresí.
size = (224, 224)
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