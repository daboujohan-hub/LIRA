"""Domaine de travail des personnes + questions auxquelles LIRA n'a pas su repondre.

- domaines.json : "projet:user_id" -> domaine  (une seule valeur par personne)
- manques.json  : question normalisee -> compteur par domaine (SANS identifiant de personne)
"""
import json
import os
import re
import tempfile
import threading
import unicodedata
from datetime import date

from learning import MAX_QUESTION, _contient_prive

DOMAINES_PATH = "domaines.json"
MANQUES_PATH = "manques.json"
MAX_MANQUES = 5000
_verrou = threading.Lock()

DOMAINES = ["sante", "informatique", "education", "commerce", "droit",
            "agriculture", "finance", "transport", "artisanat", "autre"]

ALIAS = {
    "sante": ["sante", "santé", "medecin", "médecin", "docteur", "infirmier", "infirmiere",
              "infirmière", "pharmacien", "pharmacie", "hopital", "hôpital"],
    "informatique": ["informatique", "informaticien", "developpeur", "développeur", "dev",
                     "programmeur", "programmation", "tech", "reseau", "réseau"],
    "education": ["education", "éducation", "ecole", "école", "eleve", "élève", "etudiant",
                  "étudiant", "enseignant", "professeur", "prof", "maitre", "maître"],
    "commerce": ["commerce", "commercant", "commerçant", "vente", "vendeur", "boutique"],
    "droit": ["droit", "juriste", "avocat", "justice"],
    "agriculture": ["agriculture", "agriculteur", "paysan", "planteur", "elevage", "élevage"],
    "finance": ["finance", "comptable", "comptabilite", "comptabilité", "banque", "banquier"],
    "transport": ["transport", "chauffeur", "taxi", "livreur", "logistique"],
    "artisanat": ["artisanat", "artisan", "couturier", "couture", "mecanicien", "mécanicien",
                  "menuisier", "coiffeur", "coiffure"],
    "autre": ["autre"],
}


def _slug(t):
    t = unicodedata.normalize("NFKD", t.strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def normaliser_domaine(texte):
    """Retourne un domaine de la liste, ou None si on ne le reconnait pas."""
    s = _slug(texte or "")
    if not s:
        return None
    for dom, mots in ALIAS.items():
        if s in {_slug(m) for m in mots}:
            return dom
    return None


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(chemin)) or ".")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)


def definir_domaine(cle, domaine):
    with _verrou:
        d = _lire(DOMAINES_PATH, {})
        d[cle] = domaine
        _ecrire(DOMAINES_PATH, d)


def domaine_de(cle):
    return _lire(DOMAINES_PATH, {}).get(cle)


def _canon(q):
    q = re.sub(r"\s+", " ", q.strip().lower())
    q = re.sub(r"\s+([?!.,;:])", r"\1", q)
    return q.rstrip("?!. ")


def noter_manque(question, domaine=None):
    """Compte une question sans reponse. Ignore les questions trop longues ou privees."""
    q = question.strip()
    if not q or len(q) > MAX_QUESTION or _contient_prive(q):
        return
    cle = _canon(q)
    with _verrou:
        m = _lire(MANQUES_PATH, {})
        e = m.setdefault(cle, {"question": q, "n": 0, "domaines": {}, "derniere": ""})
        e["n"] += 1
        e["derniere"] = date.today().isoformat()
        e["domaines"][domaine or "inconnu"] = e["domaines"].get(domaine or "inconnu", 0) + 1
        if len(m) > MAX_MANQUES:
            for k in sorted(m, key=lambda x: m[x]["n"])[: len(m) - MAX_MANQUES]:
                del m[k]
        _ecrire(MANQUES_PATH, m)

