import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, TOP_K


class VectorDB:
    def __init__(self, index_dir, documents=None):
        self.index_dir = index_dir
        self.index_path = os.path.join(index_dir, "medicaments.index")
        self.chunks_path = os.path.join(index_dir, "chunks.json")

        if os.path.exists(self.index_path) and os.path.exists(self.chunks_path):
            self._load()
        elif documents is not None:
            self._create(documents)
        else:
            raise Exception("Index introuvable. Lance d'abord indexation.py")

    def _get_embeddings(self, textes):
        return self.model.encode(textes, show_progress_bar=True, convert_to_numpy=True)

    def _create(self, documents):
        print("Création de la base vectorielle...")
        print(f"  Modèle d'embedding : {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        textes = [doc["contenu"] for doc in documents]
        vecteurs = self._get_embeddings(textes).astype(np.float32)

        dimension = vecteurs.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(vecteurs)
        self.documents = documents

        self._save()
        print(f"  {self.index.ntotal} vecteurs indexés")

    def _load(self):
        print("Chargement de la base vectorielle...")
        print(f"  Modèle d'embedding : {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.index = faiss.read_index(self.index_path)
        with open(self.chunks_path, "r", encoding="utf-8") as f:
            self.documents = json.load(f)
        nb_medicaments = len(set(d["metadata"]["medicament"] for d in self.documents))
        print(f"  {self.index.ntotal} chunks chargés pour {nb_medicaments} médicaments")

    def _save(self):
        os.makedirs(self.index_dir, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.chunks_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)
        print(f"  Base sauvegardée dans '{self.index_dir}/'")

    def retrieve(self, question, k=TOP_K):
        vecteur = self.model.encode([question], convert_to_numpy=True).astype(np.float32)
        scores, indices = self.index.search(vecteur, k)

        resultats = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            resultats.append({
                "contenu": self.documents[idx]["contenu"],
                "metadata": self.documents[idx]["metadata"],
                "score": float(score),
            })

        return resultats
