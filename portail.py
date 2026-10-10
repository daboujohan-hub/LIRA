"""Partie serveur du site de LIRA.

Routes publiques (sans cle, avec limites par visiteur) :
  GET  /                    la page du site (portail/index.html)
  POST /site/demo           poser une question
  GET  /site/categories     categories pour le formulaire "former LIRA"
  POST /site/demande-cle    demander une cle d'API -> code de suivi
  POST /site/statut-cle     suivre sa demande ; la cle s'affiche UNE fois si acceptee
  POST /site/former         proposer une connaissance (relue avant ajout)

Validation des demandes de cle : python gestion_demandes.py
"""
import glob
import hashlib
import io
import json
import os
import re
import secrets
import tempfile
import threading
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta

from flask import Response, jsonify, request, send_from_directory

from cle import charger_cles, cle_requise, hacher
from domaines import MANQUES_PATH, noter_manque, normaliser_domaine
from gestion_cles import sauver as sauver_cles
from learning import MAX_QUESTION, MAX_REPONSE, _contient_prive, categories_autorisees

BASE = os.path.dirname(os.path.abspath(__file__))
PORTAIL_DIR = os.path.join(BASE, "portail")
DEMANDES_PATH = os.path.abspath("demandes_cles.json")   # dossier de donnees = dossier courant
DROITS_DEMANDABLES = ["ask", "propose", "generer"]
MAX_EN_ATTENTE = 500
EXPIRATION_CLE = timedelta(days=7)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
FORMAT_DATE = "%Y-%m-%d %H:%M:%S"

_verrou = threading.Lock()
_hits = {}
_verrou_hits = threading.Lock()


# ---------------------------------------------------------------- limites
def ip_client():
    if os.environ.get("LIRA_PROXY") == "1":          # derriere le proxy de l'hebergeur (Railway)
        ip = request.headers.get("X-Real-IP", "").strip()
        if ip:
            return ip
    return request.remote_addr or "?"


def limite(nom, maxi, secondes):
    """True si la requete est autorisee, False si le visiteur depasse sa limite."""
    cle = (nom, ip_client())
    maintenant = time.time()
    with _verrou_hits:
        if len(_hits) > 20000:
            for k in [k for k, v in _hits.items() if not v or v[-1] < maintenant - 3600]:
                del _hits[k]
        liste = [t for t in _hits.get(cle, []) if t > maintenant - secondes]
        if len(liste) >= maxi:
            _hits[cle] = liste
            return False
        liste.append(maintenant)
        _hits[cle] = liste
        return True


# ---------------------------------------------------------------- stockage
def _hash_code(code):
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def _lire():
    try:
        with open(DEMANDES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DEMANDES_PATH))   # fichier prive (0600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DEMANDES_PATH)


def _slug(t, maxi=18):
    t = unicodedata.normalize("NFKD", t.strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "", t)[:maxi]
    return t if len(t) >= 2 else "projet"


def _nouveau_code():
    return "LIRA-" + "".join(secrets.choice(ALPHABET) for _ in range(5)) + "-" + \
           "".join(secrets.choice(ALPHABET) for _ in range(5))


# ---------------------------------------------------------------- administration
def _trouver(d, did):
    did = did.strip().upper()
    for h, dem in d.items():
        if dem["id"] == did:
            return h, dem
    raise ValueError(f"Demande {did} introuvable.")


def lister_demandes(tout=False):
    d = _lire()
    return sorted((v for v in d.values() if tout or v["statut"] == "en_attente"),
                  key=lambda v: v["id"])


def approuver(did, droits=None):
    """Cree la cle et la garde 7 jours pour que le demandeur la retire (une seule fois)."""
    with _verrou:
        d = _lire()
        _, dem = _trouver(d, did)
        if dem["statut"] != "en_attente":
            raise ValueError(f"{dem['id']} est deja {dem['statut']}.")
        droits = droits or dem["droits"]
        if not droits or not set(droits) <= set(DROITS_DEMANDABLES):
            raise ValueError("Droits possibles : " + ", ".join(DROITS_DEMANDABLES))
        nom = f"{_slug(dem['projet'])}-{dem['id'].lower().replace('-', '')}"
        liste = charger_cles()
        if any(c["nom"] == nom for c in liste):
            raise ValueError("Une cle porte deja ce nom.")
        cle = "lira_" + secrets.token_urlsafe(32)
        liste.append({"nom": nom, "projet": nom, "droits": list(droits), "hash": hacher(cle),
                      "actif": True, "cree": datetime.now().strftime(FORMAT_DATE)})
        sauver_cles(liste)
        dem.update(statut="approuvee", nom_cle=nom, droits=list(droits), cle=cle,
                   approuvee_le=datetime.now().strftime(FORMAT_DATE))
        _ecrire(d)
        return nom, list(droits)


def refuser(did, raison=""):
    with _verrou:
        d = _lire()
        _, dem = _trouver(d, did)
        if dem["statut"] != "en_attente":
            raise ValueError(f"{dem['id']} est deja {dem['statut']}.")
        dem.update(statut="refusee", raison=raison.strip()[:200])
        _ecrire(d)


# ---------------------------------------------------------------- routes
def installer_portail(app, engine, learning):
    @app.route("/", methods=["GET"])
    def site_accueil():
        return send_from_directory(PORTAIL_DIR, "index.html")

    @app.after_request
    def entetes_site(r):
        if request.path == "/" or request.path.startswith("/site/"):
            r.headers["X-Content-Type-Options"] = "nosniff"
            r.headers["Cache-Control"] = "no-store" if request.path != "/" else "no-cache"
        if request.path == "/":
            r.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        return r

    def erreur(msg, code=400):
        return jsonify({"error": msg}), code

    @app.route("/site/demo", methods=["POST"])
    def site_demo():
        if not limite("demo", 20, 60):
            return erreur("Trop de questions d'un coup. Attends une minute.", 429)
        q = str((request.get_json(silent=True) or {}).get("question", "")).strip()
        if not q or len(q) > MAX_QUESTION:
            return erreur("Écris une question de moins de %d caractères." % MAX_QUESTION)
        if _contient_prive(q):
            return erreur("Retire les informations personnelles de ta question.")
        reponse, _, _ = engine.ask(q)
        if reponse:
            return jsonify({"connu": True, "reponse": reponse})
        noter_manque(q, None)
        return jsonify({"connu": False, "message": "Je ne connais pas encore cette question."})

    @app.route("/site/categories", methods=["GET"])
    def site_categories():
        return jsonify({"categories": sorted(categories_autorisees())})

    @app.route("/site/demande-cle", methods=["POST"])
    def site_demande_cle():
        if not limite("demande", 5, 3600):
            return erreur("Trop de demandes. Réessaie dans une heure.", 429)
        data = request.get_json(silent=True) or {}
        projet = str(data.get("projet", "")).strip()
        usage = str(data.get("usage", "")).strip()
        contact = str(data.get("contact", "")).strip()
        droits = data.get("droits", [])
        if not (2 <= len(projet) <= 60):
            return erreur("Le nom du projet doit faire entre 2 et 60 caractères.")
        if not (10 <= len(usage) <= 400):
            return erreur("Décris ton projet en 10 à 400 caractères.")
        if len(contact) > 120:
            return erreur("Le contact est trop long.")
        if not isinstance(droits, list) or not droits or not set(droits) <= set(DROITS_DEMANDABLES):
            return erreur("Choisis au moins un besoin dans la liste.")
        with _verrou:
            d = _lire()
            if sum(1 for v in d.values() if v["statut"] == "en_attente") >= MAX_EN_ATTENTE:
                return erreur("Trop de demandes en attente pour le moment. Réessaie plus tard.", 503)
            code = _nouveau_code()
            numero = 1 + max([int(v["id"].split("-")[1]) for v in d.values()] or [0])
            d[_hash_code(code)] = {
                "id": f"D-{numero:04d}", "projet": projet, "usage": usage, "contact": contact,
                "droits": sorted(set(droits)), "statut": "en_attente",
                "cree": datetime.now().strftime(FORMAT_DATE)}
            _ecrire(d)
        return jsonify({"code": code})

    @app.route("/site/statut-cle", methods=["POST"])
    def site_statut_cle():
        if not limite("statut", 30, 3600):
            return erreur("Trop d'essais. Réessaie dans une heure.", 429)
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip()
        with _verrou:
            d = _lire()
            dem = d.get(_hash_code(code)) if code else None
            if not dem:
                return erreur("Code inconnu. Vérifie-le et réessaie.", 404)
            st = dem["statut"]
            if st == "en_attente":
                return jsonify({"statut": "en_attente"})
            if st == "refusee":
                return jsonify({"statut": "refusee", "raison": dem.get("raison", "")})
            cle = dem.get("cle")
            if not cle:
                return jsonify({"statut": "approuvee"})            # deja retiree
            age = datetime.now() - datetime.strptime(dem["approuvee_le"], FORMAT_DATE)
            if age > EXPIRATION_CLE:                               # jamais retiree : on la detruit
                liste = charger_cles()
                for c in liste:
                    if c["nom"] == dem["nom_cle"]:
                        c["actif"] = False
                sauver_cles(liste)
                dem["cle"] = None
                dem["statut"] = "expiree"
                _ecrire(d)
                return jsonify({"statut": "expiree"})
            dem["cle"] = None                                      # affichee une seule fois
            _ecrire(d)
            return jsonify({"statut": "approuvee", "cle": cle})

    @app.route("/site/former", methods=["POST"])
    def site_former():
        if not limite("former", 10, 3600):
            return erreur("Trop de propositions. Réessaie dans une heure.", 429)
        data = request.get_json(silent=True) or {}
        q = str(data.get("question", "")).strip()
        r = str(data.get("reponse", "")).strip()
        if len(q) < 5 or len(r) < 5:
            return erreur("Écris une question et une réponse complètes.")
        dom = normaliser_domaine(str(data.get("domaine", ""))) or "-"
        cat = re.sub(r"[^a-z0-9_]", "", str(data.get("categorie", "general")).lower())[:30] or "general"
        try:
            learning.propose(q, r, f"site:{dom}:{cat}")
        except ValueError as e:
            return erreur(str(e))
        return jsonify({"message": "Proposition enregistrée, en attente de relecture."})

    # ------------------------------------------------ administration a distance (cle admin)
    @app.route("/admin/demandes", methods=["GET"])
    @cle_requise("admin")
    def admin_demandes():
        tout = request.args.get("tout") == "1"
        champs = ("id", "statut", "projet", "usage", "contact", "droits", "cree", "raison")
        return jsonify([{k: d.get(k) for k in champs} for d in lister_demandes(tout)])

    @app.route("/admin/demandes/approuver", methods=["POST"])
    @cle_requise("admin")
    def admin_approuver():
        data = request.get_json(silent=True) or {}
        droits = data.get("droits") or None
        try:
            nom, droits = approuver(str(data.get("id", "")), droits)
        except ValueError as e:
            return erreur(str(e))
        return jsonify({"message": "Approuvee.", "cle_nom": nom, "droits": droits})

    @app.route("/admin/demandes/refuser", methods=["POST"])
    @cle_requise("admin")
    def admin_refuser():
        data = request.get_json(silent=True) or {}
        try:
            refuser(str(data.get("id", "")), str(data.get("raison", "")))
        except ValueError as e:
            return erreur(str(e))
        return jsonify({"message": "Refusee."})

    @app.route("/admin/manques", methods=["GET"])
    @cle_requise("admin")
    def admin_manques():
        try:
            with open(MANQUES_PATH, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            m = {}
        dom = request.args.get("domaine")
        lignes = []
        for e in m.values():
            n = e["domaines"].get(dom, 0) if dom else e["n"]
            if n:
                lignes.append({"n": n, "question": e["question"],
                               "domaine": max(e["domaines"], key=e["domaines"].get)})
        lignes.sort(key=lambda x: -x["n"])
        return jsonify(lignes[:int(request.args.get("max", 50))])

    @app.route("/admin/sauvegarde", methods=["GET"])
    @cle_requise("admin")
    def admin_sauvegarde():
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
            for chemin in sorted(glob.glob("*.json")):
                z.write(chemin)
        nom = "lira_sauvegarde_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".zip"
        return Response(tampon.getvalue(), mimetype="application/zip",
                        headers={"Content-Disposition": f"attachment; filename={nom}"})
