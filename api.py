import re
import json
from flask import Flask, request, jsonify, g
from engine import LiraEngine
from learning import LearningSystem
from generateur.generator import generer as generer_projet
from cle import cle_requise
from personnes import identifier, definir_nom, noter_question

app = Flask(__name__)
engine = LiraEngine("knowledge.json")
learning = LearningSystem(engine)

from portail import installer_portail
installer_portail(app, engine, learning)

with open("identity.json", "r", encoding="utf-8") as f:
    IDENTITY = json.load(f)


@app.route("/about", methods=["GET"])
def about():
    return jsonify(IDENTITY)


SALUTATIONS = {"salut", "bonjour", "bonsoir", "coucou", "hey", "hello",
               "slt", "bjr", "cc", "yo"}


def personnaliser(reponse, question, nom):
    """Ajoute le prenom dans une salutation : Salut ! -> Salut Koffi !"""
    if not reponse or not nom:
        return reponse
    q = re.sub(r"[^\w\s]", " ", question.lower()).split()
    if not q or len(q) > 2 or q[0] not in SALUTATIONS:
        return reponse
    return re.sub(r"^([^\W\d_]+)\s*!",
                  lambda m: f"{m.group(1)} {nom} !", reponse, count=1)


from domaines import (DOMAINES, definir_domaine, domaine_de,
                      noter_manque, normaliser_domaine)
from flask import g as _g


@app.route("/personne/domaine", methods=["POST"])
@cle_requise("ask")
def route_domaine():
    data = request.get_json() or {}
    user_id = data.get("user_id", "").strip()
    projet = ((getattr(_g, "cle", None) or {}).get("projet")
              or data.get("projet", "")).strip()
    if not user_id or not projet:
        return jsonify({"error": "user_id requis"}), 400
    dom = normaliser_domaine(data.get("domaine", ""))
    if not dom:
        return jsonify({"error": "domaine inconnu", "domaines": DOMAINES}), 400
    definir_domaine(f"{projet}:{user_id}", dom)
    return jsonify({"message": "Domaine enregistre.", "domaine": dom})


@app.route("/ask", methods=["POST"])
@cle_requise("ask")
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "question manquante"}), 400

    projet = g.cle["projet"]
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400
    cle = f"{projet}:{user_id}"
    profil, nouveau = identifier(cle)
    reponse, score, entry = engine.ask(question)
    reponse = personnaliser(reponse, question, profil.get('nom'))
    domaine = domaine_de(cle)
    if not reponse:
        noter_manque(question, domaine)
    noter_question(cle, question, bool(reponse))
    base = {"nouveau": nouveau, "nom": profil["nom"]}

    if reponse:
        return jsonify({
            **base, "connu": True,
            "reponse": reponse,
            "confiance": round(score, 3),
        "domaine": domaine,
        "demander_domaine": domaine is None,
            "id_connaissance": entry["id"]
        })
    else:
        return jsonify({
            **base, "connu": False,
            "message": "Je ne connais pas encore cette question.",
            "confiance": round(score, 3),
            "peut_proposer": True
        })


@app.route("/knowledge/propose", methods=["POST"])
@cle_requise("propose")
def propose():
    data = request.get_json()
    question = data.get("question", "").strip()
    reponse = data.get("reponse", "").strip()
    auteur = data.get("auteur", "utilisateur")

    if not question or not reponse:
        return jsonify({"error": "question et reponse requises"}), 400

    try:
        proposal = learning.propose(question, reponse, auteur)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Proposition enregistree, en attente de validation.", "proposition": proposal})


@app.route("/knowledge/pending", methods=["GET"])
@cle_requise("admin")
def pending():
    return jsonify(learning.list_pending())


@app.route("/knowledge/validate", methods=["POST"])
@cle_requise("admin")
def validate():
    data = request.get_json()
    proposal_id = data.get("id")
    categorie = data.get("categorie", "")

    try:
        entry = learning.validate(proposal_id, categorie)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if entry:
        return jsonify({"message": "Connaissance validee et integree.", "entry": entry})
    return jsonify({"error": "proposition introuvable ou deja traitee"}), 404


@app.route("/knowledge/reject", methods=["POST"])
@cle_requise("admin")
def reject():
    data = request.get_json()
    proposal_id = data.get("id")
    ok = learning.reject(proposal_id)
    if ok:
        return jsonify({"message": "Proposition rejetee."})
    return jsonify({"error": "proposition introuvable"}), 404


@app.route("/generer", methods=["POST"])
@cle_requise("generer")
def route_generer():
    data = request.get_json()
    categorie = data.get("categorie", "").strip()
    type_template = data.get("type", "").strip()
    nom = data.get("nom", "").strip()
    couleur = data.get("couleur", "#2c3e50").strip()

    if not categorie or not type_template or not nom:
        return jsonify({"error": "categorie, type et nom sont requis"}), 400

    try:
        chemin_zip = generer_projet(
            categorie, type_template, nom,
            {"NOM": nom, "COULEUR": couleur, "DESCRIPTION": f"Généré automatiquement pour {nom}"}
        )
        return jsonify({"message": "Projet généré avec succès.", "fichier": chemin_zip})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/personne/nom", methods=["POST"])
@cle_requise("ask")
def route_nom():
    data = request.get_json()
    cle = f"{g.cle['projet']}:{data.get('user_id', '').strip()}"
    nom = data.get("nom", "").strip()
    if not nom:
        return jsonify({"error": "nom requis"}), 400
    definir_nom(cle, nom)
    return jsonify({"message": f"Enchantee, {nom} !"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
