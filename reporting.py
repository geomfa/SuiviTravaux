"""
Logique métier de génération des rapports Word (hebdo + réserves).
Séparé de app.py pour rester réutilisable depuis un script en ligne de commande
si besoin plus tard (tâche planifiée, notebook, etc.).
"""

import os
from datetime import date
from pathlib import Path
import streamlit as st
from io import BytesIO
from PIL import Image

import pandas as pd
import requests
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from sqlalchemy import create_engine

def get_engine(pg_conn: str):
    return create_engine(pg_conn)


def fetch_hebdo(engine, schema: str, table: str, date_debut: date, date_fin: date) -> pd.DataFrame:
    query = f"""
        SELECT * FROM {schema}.{table}
        WHERE validation = 'Approuvé'
          AND date_heure >= %(date_debut)s
          AND date_heure <= %(date_fin)s
        ORDER BY date_heure
    """
    return pd.read_sql(query, engine, params={"date_debut": date_debut, "date_fin": date_fin})


def fetch_reserves(engine, schema: str, table: str) -> pd.DataFrame:
    query = f"""
        SELECT * FROM {schema}.{table}
        WHERE (ouverture_fnc IS NOT NULL AND ouverture_fnc NOT LIKE '')
        ORDER BY date_heure
    """
    return pd.read_sql(query, engine)


def telecharger_photo(url: str, dossier_photos: Path, id_kobo, kobo_token: str | None = None) -> Path | None:
    """Télécharge une photo si elle n'est pas déjà en cache local."""
    if not url or not isinstance(url, str):
        return None
    ext = Path(url).suffix or ".jpg"
    chemin_local = dossier_photos / f"{id_kobo}{ext}"

    if chemin_local.exists():
        if _est_image_valide(chemin_local):
            return chemin_local
        # fichier en cache invalide (ex: page d'erreur récupérée lors d'un essai précédent) : on le supprime et on retélécharge
        chemin_local.unlink(missing_ok=True)

    headers = {"Authorization": f"Token {kobo_token}"} if kobo_token else {}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            print(f"Photo {id_kobo} ignorée : réponse non-image reçue ({content_type or 'type inconnu'}). "
                  f"Vérifier si l'URL nécessite une authentification (KOBO_TOKEN).")
            return None
        img = Image.open(BytesIO(r.content))
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        clean.save(chemin_local,format="JPEG",quality=75)

        if not _est_image_valide(chemin_local):
            chemin_local.unlink(missing_ok=True)
            print(f"Photo {id_kobo} ignorée : fichier téléchargé mais non reconnu comme image valide.")
            return None
        return chemin_local
    except requests.RequestException as e:
        print(f"Échec téléchargement photo {id_kobo} : {e}")
        return None


def _est_image_valide(chemin: Path) -> bool:
    """Vérifie que le fichier est une image lisible (pas une page d'erreur, pas un fichier tronqué)."""
    try:
        from PIL import Image
        with Image.open(chemin) as img:
            img.verify()
        return True
    except Exception:
        return False


def generer_hebdo(df: pd.DataFrame, config_dir, semaine_label: str, kobo_token: str | None = None) -> Path:
    BASE_DIR = Path(config_dir)
    TEMPLATE_HEBDO = (
        BASE_DIR
        / "modeles"
        / "Fiche_Suivi_hebdo_modele_tagged.docx"
    )

    DOSSIER_PHOTOS = BASE_DIR / "photos_tmp"
    DOSSIER_SORTIE  = BASE_DIR / "sorties"
    DOSSIER_PHOTOS.mkdir(parents=True,exist_ok=True)
    DOSSIER_SORTIE.mkdir(parents=True,exist_ok=True)

    tpl = DocxTemplate(str(TEMPLATE_HEBDO))
    observations = []
    status_text = st.empty()
    for i, row in enumerate(df.itertuples(), start=1):
        if st.session_state.stop_download:
            break
        photo_path = telecharger_photo(getattr(row, "photo", None),DOSSIER_PHOTOS, row.id_kobo, kobo_token)
        status_text.text(f"Téléchargement des photos : {i}/{len(df)}")
        observations.append({
            "numero": f"{i:02d}",
            "entete": getattr(row, "intervenant", "") or "",
            "commentaire": getattr(row, "desc_prestation", "") or "",
            "prereserve": getattr(row, "desc_fnc", "") or "",
            "photo": InlineImage(tpl, str(photo_path), width=Mm(60)) if photo_path else "",
            "date": row.date_heure.strftime("%d/%m/%y") if pd.notnull(row.date_heure) else "",
            "heure": row.date_heure.strftime("%Hh%M") if pd.notnull(row.date_heure) else "",
            "interv_init": (getattr(row, "enqueteur", "") or "")[:4].upper(),
        })
    tpl.render({"semaine_label": semaine_label, "observations": observations})
    sortie = DOSSIER_SORTIE / f"Fiche_Suivi_hebdo_{date.today().isoformat()}.docx"
    tpl.save(str(sortie))
    return sortie


def generer_reserves(df: pd.DataFrame, config_dir, kobo_token: str | None = None) -> Path:
    BASE_DIR = Path(config_dir)
    TEMPLATE_RESERVES = (
        BASE_DIR
        / "modeles"
        / "Fiche_Annexe_Reserve_vf_modele_tagged.docx"
    )

    DOSSIER_PHOTOS = BASE_DIR / "photos_tmp"
    DOSSIER_SORTIE  = BASE_DIR / "sorties"
    DOSSIER_PHOTOS.mkdir(parents=True,exist_ok=True)
    DOSSIER_SORTIE.mkdir(parents=True,exist_ok=True)

    tpl = DocxTemplate(str(TEMPLATE_RESERVES))
    reserves = []
    status_text = st.empty()
    for i, row in enumerate(df.itertuples(), start=1):
        if st.session_state.stop_download:
            break
        photo_path = telecharger_photo(getattr(row, "photo", None), DOSSIER_PHOTOS, row.id_kobo, kobo_token)
        status_text.text(f"Téléchargement des photos : {i}/{len(df)}")
        reserves.append({
            "numero": i,
            "titre": f"{getattr(row, 'prestation', '') or ''} | {getattr(row, 'activite', '') or ''}",
            "description": getattr(row, "desc_fnc", "") or "",
            "photo": InlineImage(tpl, str(photo_path), width=Mm(60)) if photo_path else "",
        })
    tpl.render({"reserves": reserves})
    sortie = DOSSIER_SORTIE / f"Fiche_Annexe_Reserves_{date.today().isoformat()}.docx"
    tpl.save(str(sortie))
    return sortie
