import os
from groq import Groq
from dotenv import load_dotenv

from config import GROQ_MODEL, INDEX_DIR, PROMPT_PATH, SEUIL_SCORE
from vector_db import VectorDB


class RAG:
    def __init__(self):
        load_dotenv()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.vector_db = VectorDB(INDEX_DIR)
        self.historique = []
        self.attend_clarification = False

    def _read_prompt(self) -> str:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def _construire_requete_faiss(self, question: str) -> str:
        # On combine les questions précédentes avec la question actuelle
        # pour que les clarifications enrichissent la recherche vectorielle
        questions_precedentes = [
            msg["content"] for msg in self.historique if msg["role"] == "user"
        ]
        if questions_precedentes:
            return " ".join(questions_precedentes) + " " + question
        return question

    def _construire_contexte(self, resultats: list) -> str:
        contexte = ""
        for i, r in enumerate(resultats, 1):
            meta = r["metadata"]
            contexte += f"\n--- Extrait {i} ---\n"
            contexte += f"Médicament : {meta['medicament']}\n"
            contexte += f"Section : {meta['section']}\n"
            contexte += f"Contenu : {r['contenu']}\n"
        return contexte

    def _generer_reponse(self, question: str, resultats: list) -> str:
        if resultats and resultats[0]["score"] <= SEUIL_SCORE:
            contexte = self._construire_contexte(resultats)
        else:
            contexte = "Aucun extrait pertinent trouvé pour cette question."

        messages = [{"role": "system", "content": self._read_prompt()}]
        messages += self.historique
        messages.append({
            "role": "user",
            "content": f"Contexte (extraits de notices officielles) :\n{contexte}\n\nQuestion : {question}"
        })

        reponse = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return reponse.choices[0].message.content

    def _afficher_sources(self, resultats: list):
        print("\n  Sources :")
        medicaments_cites = set()
        for r in resultats:
            meta = r["metadata"]
            cle = f"{meta['medicament']} — {meta['section']}"
            if cle not in medicaments_cites:
                print(f"    • {cle}")
                medicaments_cites.add(cle)

    def answer(self, question: str):
        requete_faiss = self._construire_requete_faiss(question)
        resultats = self.vector_db.retrieve(requete_faiss)
        reponse = self._generer_reponse(question, resultats)

        self.historique.append({"role": "user", "content": question})
        self.historique.append({"role": "assistant", "content": reponse})

        return reponse, resultats

    def run(self):
        print("=" * 50)
        print("  Assistant Médicaments RAG")
        print("=" * 50)
        print("\nSystème prêt. Tapez 'quit' pour quitter.\n")

        while True:
            invite = "Votre réponse : " if self.attend_clarification else "Votre question : "
            question = input(invite).strip()

            if question.lower() in ["quit", "exit", "q"]:
                print("Au revoir !")
                break

            if not question:
                continue

            print("\nRecherche en cours...\n")
            reponse, resultats = self.answer(question)

            print(f"Réponse :\n{reponse}")

            resultats_pertinents = bool(resultats) and resultats[0]["score"] <= SEUIL_SCORE
            est_une_reponse = "⚠️" in reponse
            if est_une_reponse and resultats_pertinents:
                self._afficher_sources(resultats)

            print("\n" + "-" * 50 + "\n")
            self.attend_clarification = not est_une_reponse


if __name__ == "__main__":
    rag = RAG()
    rag.run()
