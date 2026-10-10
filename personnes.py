import json
import os
from datetime import datetime

PERSONNES_PATH = "personnes.json"


def _charger():
    if os.path.exists(PERSONNES_PATH):
        with open(PERSONNES_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def _sauver(data):
    with open(PERSONNES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def identifier(user_id):
    """Retourne (profil, est_nouveau). Crée le profil si inconnu."""
    data = _charger()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nouveau = user_id not in data
    if nouveau:
        data[user_id] = {
            "nom": None,
            "premiere_visite": maintenant,
            "derniere_visite": maintenant,
            "questions": [],
        }
    else:
        data[user_id]["derniere_visite"] = maintenant
    _sauver(data)
    return data[user_id], nouveau


def definir_nom(user_id, nom):
    data = _charger()
    if user_id in data:
        data[user_id]["nom"] = nom
        _sauver(data)


def noter_question(user_id, question, connue):
    data = _charger()
    if user_id in data:
        data[user_id]["questions"].append({
            "question": question,
            "connue": connue,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        _sauver(data)
