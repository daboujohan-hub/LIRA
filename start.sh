#!/bin/sh
# Demarrage sur Railway : les donnees vivent sur le volume (/data), le code dans /srv/lira.
set -e
DATA="${DATA_DIR:-/data}"
mkdir -p "$DATA"
cd "$DATA"

# connaissances de depart : copiees une seule fois, jamais ecrasees
for f in /srv/lira/seed/*; do
  [ -e "$(basename "$f")" ] || cp "$f" .
done
[ -e generateur ] || { [ -d /srv/lira/generateur ] && ln -s /srv/lira/generateur generateur; }

# premiere cle admin : creee a partir de LIRA_ADMIN_HASH (le hash, jamais la cle elle-meme)
if [ ! -f cles.json ]; then
  python - <<'PY'
import json, os, re, sys
h = os.environ.get("LIRA_ADMIN_HASH", "").strip().lower()
if not re.fullmatch(r"[0-9a-f]{64}", h):
    sys.exit("ERREUR : la variable LIRA_ADMIN_HASH doit etre un hash SHA-256 (64 caracteres 0-9 a-f).")
json.dump([{"nom": "prod-admin", "projet": "prod", "droits": ["admin"], "hash": h,
            "actif": True, "cree": "premier demarrage"}], open("cles.json", "w"), indent=2)
print("cles.json cree avec la cle admin.")
PY
fi

# 1 seul processus : LIRA garde ses donnees en memoire et dans des fichiers
exec gunicorn api:app --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 60
