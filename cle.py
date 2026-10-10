import hashlib
import hmac
import json
import os
from functools import wraps

from flask import g, jsonify, request

CLES_PATH = "cles.json"


def hacher(cle):
    return hashlib.sha256(cle.encode("utf-8")).hexdigest()


def charger_cles():
    if os.path.exists(CLES_PATH):
        with open(CLES_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def cle_requise(droit):
    def decorateur(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            h = hacher(request.headers.get("X-API-Key", ""))
            for entree in charger_cles():
                if hmac.compare_digest(entree["hash"], h):
                    if not entree.get("actif"):
                        return jsonify({"error": "cle revoquee"}), 401
                    droits = entree["droits"]
                    if droit not in droits and "admin" not in droits:
                        return jsonify({"error": f"droit '{droit}' manquant"}), 403
                    g.cle = entree
                    return f(*args, **kwargs)
            return jsonify({"error": "acces refuse"}), 401
        return wrapper
    return decorateur
