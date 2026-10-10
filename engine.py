import json
import random
import os
import re
import math
from collections import Counter
from markov import GenerateurMarkov
from synonymes import normaliser_synonyme

SEUIL_CONFIANCE = 0.65  # à ajuster selon tes tests

# Suffixes courants à retirer, du plus long au plus court,
# pour ramener les mots à une forme proche de leur racine.
SUFFIXES = [
    "issions", "issaient", "eraient", "assions",
    "ations", "ement", "ition", "ance",
    "ees", "ais", "ait", "ant", "ent",
    "ee", "es", "er", "ir", "re", "s",
]


def alleger_suffixe(mot):
    """Retire un suffixe grammatical courant si le mot est assez long."""
    if len(mot) <= 4:
        return mot
    for suffixe in SUFFIXES:
        if mot.endswith(suffixe) and len(mot) - len(suffixe) >= 3:
            return mot[: -len(suffixe)]
    return mot


def tokenize(texte):
    """Découpe un texte en mots simples, en minuscules, sans ponctuation,
    puis normalise chaque mot (synonymes + suffixes grammaticaux)."""
    texte = texte.lower()
    mots_bruts = re.findall(r"[a-zà-öø-ÿ0-9]+", texte)
    mots_normalises = []
    for mot in mots_bruts:
        mot = normaliser_synonyme(mot)
        mot = alleger_suffixe(mot)
        mots_normalises.append(mot)
    return mots_normalises


class LiraEngine:
    def __init__(self, knowledge_path="knowledge.json"):
        self.knowledge_path = knowledge_path
        self.knowledge = []
        self.questions_flat = []
        self.index_map = []
        self.doc_vectors = []
        self.idf = {}
        self.markov = GenerateurMarkov(ordre=2)
        self.load()

    def load(self):
        if os.path.exists(self.knowledge_path):
            with open(self.knowledge_path, "r", encoding="utf-8") as f:
                self.knowledge = json.load(f)
        else:
            self.knowledge = []
        self._build_index()
        self._entrainer_markov()

    def _entrainer_markov(self):
        textes = [entry["reponse"] for entry in self.knowledge if entry.get("reponse")]
        self.markov.entrainer(textes)

    def generer_texte(self):
        return self.markov.generer()

    def _build_index(self):
        self.questions_flat = []
        self.index_map = []

        for i, entry in enumerate(self.knowledge):
            for q in entry["questions"]:
                self.questions_flat.append(q)
                self.index_map.append(i)

        if not self.questions_flat:
            self.idf = {}
            self.doc_vectors = []
            return

        tokenized_docs = [tokenize(q) for q in self.questions_flat]
        n_docs = len(tokenized_docs)

        df = Counter()
        for tokens in tokenized_docs:
            for mot in set(tokens):
                df[mot] += 1

        self.idf = {
            mot: math.log((n_docs + 1) / (freq + 1)) + 1
            for mot, freq in df.items()
        }

        self.doc_vectors = []
        for tokens in tokenized_docs:
            self.doc_vectors.append(self._vectorize(tokens))

    def _vectorize(self, tokens):
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        vecteur = {}
        for mot, freq in tf.items():
            tf_val = freq / total
            idf_val = self.idf.get(mot, math.log(len(self.doc_vectors) + 1) + 1) if self.doc_vectors else 1
            vecteur[mot] = tf_val * idf_val
        return vecteur

    def _cosine_similarity(self, vec1, vec2):
        mots_communs = set(vec1.keys()) & set(vec2.keys())
        produit_scalaire = sum(vec1[m] * vec2[m] for m in mots_communs)

        norme1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norme2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        if norme1 == 0 or norme2 == 0:
            return 0.0

        return produit_scalaire / (norme1 * norme2)

    def ask(self, question):
        if not self.questions_flat:
            return None, 0.0, None

        tokens = tokenize(question)
        vecteur_question = self._vectorize(tokens)

        meilleur_score = 0.0
        meilleur_idx = -1

        for i, vec in enumerate(self.doc_vectors):
            score = self._cosine_similarity(vecteur_question, vec)
            if score > meilleur_score:
                meilleur_score = score
                meilleur_idx = i

        seuil_applique = SEUIL_CONFIANCE
        if len(tokens) <= 1:
            seuil_applique = 0.90
        elif len(tokens) == 2:
            seuil_applique = 0.75

        if meilleur_score >= seuil_applique and meilleur_idx != -1:
            entry_idx = self.index_map[meilleur_idx]
            entry = self.knowledge[entry_idx]
            return self.choisir_reponse(entry), meilleur_score, entry

        return None, meilleur_score, None

    def choisir_reponse(self, entry):
        """Choisit au hasard parmi la reponse et ses variantes, sans repeter la precedente."""
        choix = [entry["reponse"]] + [v for v in entry.get("variantes", []) if v and v.strip()]
        if len(choix) == 1:
            return choix[0]
        if not hasattr(self, "_dernieres"):
            self._dernieres = {}
        derniere = self._dernieres.get(entry["id"])
        possibles = [c for c in choix if c != derniere] or choix
        rep = random.choice(possibles)
        self._dernieres[entry["id"]] = rep
        return rep

    def save(self):
        with open(self.knowledge_path, "w", encoding="utf-8") as f:
            json.dump(self.knowledge, f, ensure_ascii=False, indent=2)

    def add_knowledge(self, question, reponse, categorie="general"):
        max_num = 0
        for entry in self.knowledge:
            try:
                num = int(entry["id"].split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                continue

        new_id = f"INFO-{max_num + 1:04d}"
        entry = {
            "id": new_id,
            "questions": [question],
            "reponse": reponse,
            "categorie": categorie
        }
        self.knowledge.append(entry)
        self.save()
        self._build_index()
        self._entrainer_markov()
        return entry
