# Вспомогательная функция для проверки распределения
import json
from pathlib import Path

DATA_FILE = Path("data.json")

def show_gifting_pairs():
    if not DATA_FILE.exists():
        print("Файл data.json не найден")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("started"):
        print("Игра ещё не началась")
        return

    print("Номера участников и кому они дарят:")
    for uid, info in data.get("users", {}).items():
        giver_number = info.get("number")
        receiver_number = info.get("gives_to", "не назначен")
        print(f"Участник №{giver_number} дарит участнику №{receiver_number}")

if __name__ == "__main__":
    show_gifting_pairs()