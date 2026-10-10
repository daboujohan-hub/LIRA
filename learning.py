import json
import os
import re
from datetime import datetime, timezone

PROPOSALS_PATH = "proposals.json"
CATEGORIES_PATH = "categories.json"


def categories_autorisees():
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ["general"]

MAX_QUESTION = 300
MAX_REPONSE = 1000


def _contient_secret(texte):
    """Jetons, cles API et cles privees : jamais dans la base de connaissances."""
    motifs = [r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}",
              r"lira_[A-Za-z0-9_-]{30,}", r"\bsk-[A-Za-z0-9_-]{20,}", r"\bAKIA[0-9A-Z]{16}\b",
              r"\bAIza[0-9A-Za-z_-]{35}\b", r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
              r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]
    if any(re.search(p, texte) for p in motifs):
        return "un jeton ou une cle secrete"
    return None


def _contient_prive(texte):
    s = _contient_secret(texte)
    if s:
        return s
    """Retourne le type de donnee privee trouvee, ou None."""
    for m in re.finditer(r"\+?\d[\d\s.\-]{6,}\d", texte):
        if sum(c.isdigit() for c in m.group()) >= 9:
            return "un numero de telephone"
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", texte):
        return "une adresse e-mail"
    if re.search(r"(mot de passe|password|mdp)\s*[:=]", texte, re.I):
        return "un mot de passe"
    return None


class LearningSystem:
    """Gere les propositions de connaissances non validees."""

    def __init__(self, engine):
        self.engine = engine
        self.proposals = self._load_proposals()

    def _load_proposals(self):
        if os.path.exists(PROPOSALS_PATH):
            with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_proposals(self):
        with open(PROPOSALS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.proposals, f, ensure_ascii=False, indent=2)

    def propose(self, question, proposed_answer, auteur="utilisateur"):
        question = question.strip()
        proposed_answer = proposed_answer.strip()
        auteur = (auteur or "utilisateur").strip()[:50]

        if not question or not proposed_answer:
            raise ValueError("Question et reponse requises.")
        if len(question) > MAX_QUESTION:
            raise ValueError(f"Question trop longue ({MAX_QUESTION} caracteres max).")
        if len(proposed_answer) > MAX_REPONSE:
            raise ValueError(f"Reponse trop longue ({MAX_REPONSE} caracteres max).")

        for texte in (question, proposed_answer):
            prive = _contient_prive(texte)
            if prive:
                raise ValueError(f"Refuse : le texte contient {prive}.")

        deja_connue, _, _ = self.engine.ask(question)
        if deja_connue:
            raise ValueError("Cette question est deja connue de LIRA.")

        for p in self.proposals:
            if (p["statut"] == "en_attente"
                    and p["question"].strip().lower() == question.lower()):
                raise ValueError("Une proposition identique est deja en attente.")

        proposal = {
            "id": f"PROP-{len(self.proposals) + 1:04d}",
            "question": question,
            "reponse_proposee": proposed_answer,
            "auteur": auteur,
            "date": datetime.now(timezone.utc).isoformat(),
            "statut": "en_attente",
        }
        self.proposals.append(proposal)
        self._save_proposals()
        return proposal

    def list_pending(self):
        return [p for p in self.proposals if p["statut"] == "en_attente"]

    def validate(self, proposal_id, categorie):
        categorie = (categorie or "").strip().lower()
        autorisees = categories_autorisees()
        if categorie not in autorisees:
            raise ValueError("Categorie inconnue. Autorisees : " + ", ".join(autorisees))
        for p in self.proposals:
            if p["id"] == proposal_id and p["statut"] == "en_attente":
                p["statut"] = "validee"
                self._save_proposals()
                return self.engine.add_knowledge(
                    p["question"], p["reponse_proposee"], categorie
                )
        return None

    def reject(self, proposal_id):
        for p in self.proposals:
            if p["id"] == proposal_id and p["statut"] == "en_attente":
                p["statut"] = "rejetee"
                self._save_proposals()
                return True
        return False
