import json
import re
import secrets
import sys
from datetime import datetime

from cle import CLES_PATH, charger_cles, hacher

DROITS_VALIDES = {"ask", "propose", "generer", "admin"}


def sauver(liste):
    with open(CLES_PATH, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)


def creer(nom, projet, droits_txt):
    droits = [d for d in droits_txt.split(",") if d]
    if not re.fullmatch(r"[a-z0-9_-]{2,30}", nom):
        sys.exit("Nom invalide (minuscules, chiffres, - et _).")
    if not re.fullmatch(r"[a-z0-9_-]{2,30}", projet):
        sys.exit("Projet invalide (minuscules, chiffres, - et _).")
    if not droits or not set(droits) <= DROITS_VALIDES:
        sys.exit("Droits possibles : " + ", ".join(sorted(DROITS_VALIDES)))
    liste = charger_cles()
    if any(c["nom"] == nom for c in liste):
        sys.exit("Ce nom existe deja.")
    cle = "lira_" + secrets.token_urlsafe(32)
    liste.append({
        "nom": nom,
        "projet": projet,
        "droits": droits,
        "hash": hacher(cle),
        "actif": True,
        "cree": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    sauver(liste)
    print(f"Cle creee pour '{nom}' (projet {projet}, droits {','.join(droits)}).")
    print("Copie-la maintenant, elle ne sera plus jamais affichee :\n")
    print(cle)


def lister():
    for c in charger_cles():
        etat = "actif" if c["actif"] else "REVOQUE"
        print(f"{c['nom']:<18} projet={c['projet']:<14} droits={','.join(c['droits']):<24} {etat}")


def revoquer(nom):
    liste = charger_cles()
    for c in liste:
        if c["nom"] == nom:
            c["actif"] = False
            sauver(liste)
            print(f"Cle '{nom}' revoquee.")
            return
    sys.exit("Nom introuvable.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["creer"] and len(a) == 4:
        creer(a[1], a[2], a[3])
    elif a[:1] == ["lister"]:
        lister()
    elif a[:1] == ["revoquer"] and len(a) == 2:
        revoquer(a[1])
    else:
        print("Usage :\n  python gestion_cles.py creer <nom> <projet> <droits,separes,par,virgules>\n"
              "  python gestion_cles.py lister\n  python gestion_cles.py revoquer <nom>")
