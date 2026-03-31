import random
import requests

ESP_IP = "192.168.4.1"
PING_URL = f"http://{ESP_IP}/ping"
DATA_URL = f"http://{ESP_IP}/data"

ANGLES = [0, 90, 180, 270]

stats = {
    angle: {"total": 0, "success": 0, "fail": 0}
    for angle in ANGLES
}

def print_stats():
    print("\n--- Results ---")
    for angle in ANGLES:
        total = stats[angle]["total"]
        success = stats[angle]["success"]
        fail = stats[angle]["fail"]

        if total > 0:
            percent = (success / total) * 100
        else:
            percent = 0

        print(f"{angle:>3}° -> total: {total}, success: {success}, fail: {fail}, success rate: {percent:.1f}%")
    print("---------------\n")

def main():
    try:
        r = requests.get(PING_URL, timeout=2)
        r.raise_for_status()
        print("Ping OK:", r.text)

        while True:
            angle = random.choice(ANGLES)
            payload = {"angle": angle}

            r = requests.post(DATA_URL, json=payload, timeout=2)
            r.raise_for_status()

            print(f"Sent angle: {angle}°")
            print("ESP response:", r.text)

            while True:
                result = input("Write S = success, F = fail, Q = quit: ").strip().upper()

                if result in ("S", "F", "Q"):
                    break

                print("Invalid input. Use S, F, or Q.")

            if result == "Q":
                print_stats()
                print("Program ended.")
                break

            stats[angle]["total"] += 1

            if result == "S":
                stats[angle]["success"] += 1
            else:
                stats[angle]["fail"] += 1

            print_stats()

    except requests.exceptions.RequestException as e:
        print("Request failed:", e)

if __name__ == "__main__":
    main()