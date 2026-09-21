import os
from pathlib import Path

from datetime import date, timedelta
import streamlit as st
from dotenv import load_dotenv

from reporting import get_engine, fetch_hebdo, fetch_reserves, generer_hebdo, generer_reserves

if "stop_download" not in st.session_state:
    st.session_state.stop_download = False

if "config_dir" not in st.session_state:
    st.session_state.config_dir = ""


st.set_page_config(page_title="Rapports de suivi de chantier", page_icon="🚧", layout="centered")
st.title("Rapports de suivi de chantier")

tab_config, tab_hebdo, tab_reserves = st.tabs(["Configuration","Rapport hebdomadaire", "Rapport réserves"])

with tab_config:
    st.subheader("Configuration")

    config_dir = st.text_input(
        "Saisir le chemin du dossier de configuration",
        value=st.session_state.config_dir,
        placeholder=r"C:\fichiers_config"
    )
    st.markdown('<p style="font-size:14px; color:grey;">Dossier de configuration type dans /IT_Suivi_travaux/SuiviTravaux_fichiers_config/</p>',unsafe_allow_html=True)

    if st.button("Enregistrer la configuration"):
        chemin = Path(config_dir)
        if not chemin.is_dir():
            st.error("Le dossier indiqué n'existe pas.")
        elif not (chemin / ".env").is_file():
            st.error(
                "Le fichier .env est introuvable dans ce dossier."
            )
        elif not (chemin / "modeles").is_dir():
            st.error(
                "Le dossier 'modeles' est introuvable."
            )
        else:
            st.session_state.config_dir = config_dir
            st.success(
                "Configuration enregistrée."
            )


if st.session_state.config_dir:
    CONFIG_DIR = Path(st.session_state.config_dir)

    ENV_FILE = CONFIG_DIR / ".env"

    load_dotenv(
        ENV_FILE,
        override=True
    )

    PG_CONN = os.getenv("PG_CONN", "")
    SCHEMA = os.getenv("SCHEMA", "")
    TABLE_NAME = os.getenv("TABLE_NAME", "")
    KOBO_TOKEN = os.getenv("KOBO_TOKEN", "")

    if not PG_CONN or not SCHEMA or not TABLE_NAME:
        st.error(
            "Configuration manquante. Renseigne PG_CONN, SCHEMA et TABLE_NAME dans le fichier .env "
            "(voir .env.example)."
        )
        st.stop()
else:

    CONFIG_DIR = None
    PG_CONN = ""
    SCHEMA = ""
    TABLE_NAME = ""
    KOBO_TOKEN = ""


with tab_hebdo:
    st.subheader("Fiche de suivi hebdomadaire")
    st.caption("Toutes les soumissions au statut 'Approuvé' sur la période choisie.")

    col1, col2 = st.columns(2)
    with col1:
        date_debut = st.date_input("Date de début", value=date.today() - timedelta(days=7))
    with col2:
        date_fin = st.date_input("Date de fin", value=date.today())

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Générer le rapport hebdomadaire", type="primary"):
            st.session_state.stop_download = False
            with st.spinner("Récupération des données et génération du document..."):
                engine = get_engine(PG_CONN)
                df = fetch_hebdo(engine, SCHEMA, TABLE_NAME, date_debut, date_fin)

                if df.empty:
                    st.warning("Aucune soumission approuvée trouvée sur cette période.")
                else:
                    semaine_label = f"Du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
                    chemin = generer_hebdo(df, CONFIG_DIR, semaine_label, KOBO_TOKEN or None)
                    st.success(f"Rapport généré : {len(df)} observation(s).")
                    with open(chemin, "rb") as f:
                        st.download_button(
                            "Télécharger le rapport hebdomadaire",
                            data=f.read(),
                            file_name=chemin.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
    with col2:
        if st.button("Arrêter le téléchargement des photos"):
            st.session_state.stop_download = True

with tab_reserves:
    st.subheader("Fiche annexe des réserves")
    st.caption("Tous les points marqués avec une non-conformité (FNC), tous statuts et toutes dates confondus.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Générer le rapport réserves", type="primary"):
            st.session_state.stop_download = False
            with st.spinner("Récupération des données et génération du document..."):
                engine = get_engine(PG_CONN)
                df = fetch_reserves(engine, SCHEMA, TABLE_NAME)

                if df.empty:
                    st.warning("Aucune réserve trouvée.")
                else:
                    chemin = generer_reserves(df, CONFIG_DIR, KOBO_TOKEN or None)
                    st.success(f"Rapport généré : {len(df)} réserve(s).")
                    st.info("Le champ 'Condition de levée' est laissé vide dans le document : à compléter à la main.")
                    with open(chemin, "rb") as f:
                        st.download_button(
                            "Télécharger le rapport réserves",
                            data=f.read(),
                            file_name=chemin.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
    with col2:
        if st.button("Arrêter le téléchargement des photos "):
            st.session_state.stop_download = True