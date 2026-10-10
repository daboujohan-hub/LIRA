import html
import os
import re
import shutil
import zipfile

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
SORTIE_DIR = os.path.join(os.path.dirname(__file__), "generes")

TYPES_DISPONIBLES = {
    "site": ["vitrine"],
    "app_web": ["todo"],
    "app_android": ["basique"],
}


def lister_templates():
    return TYPES_DISPONIBLES


def _remplacer_placeholders(dossier, remplacements):
    for racine, _, fichiers in os.walk(dossier):
        for nom_fichier in fichiers:
            chemin = os.path.join(racine, nom_fichier)
            try:
                with open(chemin, "r", encoding="utf-8") as f:
                    contenu = f.read()
            except UnicodeDecodeError:
                continue

            for cle, valeur in remplacements.items():
                contenu = contenu.replace(f"{{{{{cle}}}}}", valeur)

            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu)


def generer(categorie, type_template, nom_projet, remplacements):
    if categorie not in TYPES_DISPONIBLES:
        raise ValueError(f"Catégorie inconnue : {categorie}")
    if type_template not in TYPES_DISPONIBLES[categorie]:
        raise ValueError(f"Template inconnu : {type_template}")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", nom_projet):
        raise ValueError("Nom invalide : lettres, chiffres, - et _ seulement (40 max).")
    couleur = remplacements.get("COULEUR")
    if couleur is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", couleur):
        raise ValueError("Couleur invalide : format attendu #RRGGBB.")
    remplacements = {
        k: (v if k == "COULEUR" else html.escape(v))
        for k, v in remplacements.items()
    }

    dossier_categorie = {"site": "sites", "app_web": "apps_web", "app_android": "apps_android"}[categorie]
    source = os.path.join(TEMPLATES_DIR, dossier_categorie, type_template)

    dossier_sortie = os.path.join(SORTIE_DIR, nom_projet)
    if os.path.exists(dossier_sortie):
        shutil.rmtree(dossier_sortie)

    shutil.copytree(source, dossier_sortie)
    _remplacer_placeholders(dossier_sortie, remplacements)

    chemin_zip = os.path.join(SORTIE_DIR, f"{nom_projet}.zip")
    if os.path.exists(chemin_zip):
        os.remove(chemin_zip)

    with zipfile.ZipFile(chemin_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for racine, _, fichiers in os.walk(dossier_sortie):
            for nom_fichier in fichiers:
                chemin_complet = os.path.join(racine, nom_fichier)
                chemin_relatif = os.path.relpath(chemin_complet, dossier_sortie)
                zf.write(chemin_complet, os.path.join(nom_projet, chemin_relatif))

    return chemin_zip
