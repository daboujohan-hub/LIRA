# Groupes de synonymes : tous les mots d'un groupe sont ramenés
# au premier mot du groupe lors de la recherche.
GROUPES_SYNONYMES = [
    ["voiture", "automobile", "vehicule", "auto"],
    ["rapide", "vite", "rapidement", "vitesse"],
    ["lent", "lentement", "lenteur"],
    ["intelligent", "intelligente", "malin", "futee", "futee"],
    ["grand", "gros", "immense", "enorme", "grande"],
    ["petit", "minuscule", "petite", "minime"],
    ["beau", "belle", "joli", "jolie", "magnifique"],
    ["content", "heureux", "heureuse", "joyeux", "ravi"],
    ["triste", "malheureux", "malheureuse", "peine"],
    ["parler", "discuter", "converser", "causer"],
    ["manger", "bouffer", "nourrir", "alimenter"],
    ["travail", "boulot", "emploi", "job", "metier"],
    ["argent", "fric", "sous", "monnaie", "thune"],
    ["maison", "domicile", "logement", "habitation"],
    ["telephone", "portable", "mobile", "smartphone"],
    ["ordinateur", "pc", "computer", "machine"],
    ["aider", "assister", "aide", "assistance"],
    ["creer", "fabriquer", "construire", "concevoir", "faire"],
    ["expliquer", "clarifier", "detailler", "eclaircir"],
    ["comprendre", "saisir", "piger", "assimiler"],
    ["important", "essentiel", "crucial", "capital", "majeur"],
    ["difficile", "compliquee", "complique", "dur", "ardu"],
    ["facile", "simple", "aise", "basique"],
    ["question", "interrogation", "demande"],
    ["reponse", "solution", "resultat"],
    ["probleme", "souci", "difficulte", "ennui"],
    ["pays", "nation", "etat"],
    ["ville", "cite", "commune"],
    ["gens", "personnes", "monde", "individus"],
    ["enfant", "gosse", "gamin", "gamine", "bambin"],
]


def construire_dictionnaire():
    """Transforme les groupes en dictionnaire mot -> forme canonique."""
    dico = {}
    for groupe in GROUPES_SYNONYMES:
        canonique = groupe[0]
        for mot in groupe:
            dico[mot] = canonique
    return dico


DICTIONNAIRE_SYNONYMES = construire_dictionnaire()


def normaliser_synonyme(mot):
    """Remplace un mot par sa forme canonique s'il fait partie d'un groupe de synonymes."""
    return DICTIONNAIRE_SYNONYMES.get(mot, mot)
