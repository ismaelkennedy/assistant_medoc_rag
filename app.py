import streamlit as st
from config import SEUIL_SCORE, MEDICAMENTS_CIBLES
from rag import RAG


st.set_page_config(
    page_title="Assistant Médicaments",
    page_icon="💊",
    layout="centered",
)

st.title("💊 Assistant Médicaments")
st.caption("Posez vos questions sur les médicaments. Les réponses sont basées sur les notices officielles de la BDPM.")

# Initialisation du RAG une seule fois par session
if "rag" not in st.session_state:
    with st.spinner("Chargement de l'assistant..."):
        st.session_state.rag = RAG()
    st.session_state.messages = []
    st.session_state.attend_clarification = False

# Sidebar avec les médicaments disponibles
with st.sidebar:
    st.header("Médicaments disponibles")
    for med in sorted(MEDICAMENTS_CIBLES):
        st.write(f"• {med.capitalize()}")
    st.divider()
    if st.button("Nouvelle conversation"):
        st.session_state.rag.historique = []
        st.session_state.messages = []
        st.session_state.attend_clarification = False
        st.rerun()

# Affichage des messages de la conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for source in msg["sources"]:
                    st.write(f"• {source}")

# Champ de saisie
placeholder = "Votre réponse..." if st.session_state.attend_clarification else "Posez votre question..."
question = st.chat_input(placeholder)

if question:
    # Affichage du message utilisateur
    with st.chat_message("user"):
        st.write(question)
    st.session_state.messages.append({"role": "user", "content": question})

    # Génération de la réponse
    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours..."):
            reponse, resultats = st.session_state.rag.answer(question)

        st.write(reponse)

        # Sources uniquement si c'est une vraie réponse avec des chunks pertinents
        resultats_pertinents = bool(resultats) and resultats[0]["score"] <= SEUIL_SCORE
        est_une_reponse = "⚠️" in reponse

        sources = []
        if est_une_reponse and resultats_pertinents:
            medicaments_cites = set()
            for r in resultats:
                meta = r["metadata"]
                cle = f"{meta['medicament']} — {meta['section']}"
                if cle not in medicaments_cites:
                    sources.append(cle)
                    medicaments_cites.add(cle)
            if sources:
                with st.expander("Sources"):
                    for source in sources:
                        st.write(f"• {source}")

    st.session_state.messages.append({
        "role": "assistant",
        "content": reponse,
        "sources": sources,
    })

    st.session_state.attend_clarification = not est_une_reponse
