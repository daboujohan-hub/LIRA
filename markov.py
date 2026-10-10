import random
import re
from collections import defaultdict


class GenerateurMarkov:
    """Petit modèle de langage local : apprend les enchaînements de mots
    dans un corpus de textes, puis génère de nouvelles phrases inédites."""

    def __init__(self, ordre=2):
        self.ordre = ordre
        self.chaine = defaultdict(list)
        self.debuts = []

    def entrainer(self, textes):
        self.chaine = defaultdict(list)
        self.debuts = []
        for texte in textes:
            mots = self._tokenizer(texte)
            if len(mots) < self.ordre + 1:
                continue
            self.debuts.append(tuple(mots[:self.ordre]))
            for i in range(len(mots) - self.ordre):
                cle = tuple(mots[i:i + self.ordre])
                suivant = mots[i + self.ordre]
                self.chaine[cle].append(suivant)

    def _tokenizer(self, texte):
        return re.findall(r"[\wàâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ'-]+|[.,!?;]", texte)

    def generer(self, longueur_max=40):
        if not self.debuts:
            return None

        etat = random.choice(self.debuts)
        resultat = list(etat)

        for _ in range(longueur_max):
            suivants = self.chaine.get(etat)
            if not suivants:
                break
            mot = random.choice(suivants)
            resultat.append(mot)
            etat = tuple(resultat[-self.ordre:])
            if mot in (".", "!", "?") and len(resultat) > 5:
                break

        return self._reconstituer(resultat)

    def _reconstituer(self, mots):
        phrase = ""
        for mot in mots:
            if mot in (".", ",", "!", "?", ";"):
                phrase += mot
            elif phrase == "":
                phrase = mot
            else:
                phrase += " " + mot
        return phrase[0].upper() + phrase[1:] if phrase else phrase
