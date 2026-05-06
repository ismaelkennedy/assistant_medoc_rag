# Assistant Médicaments RAG

Système de questions-réponses sur les médicaments, construit avec Python, FAISS et Groq.  
Les réponses sont basées sur les notices officielles de la Base de Données Publique des Médicaments (BDPM).


## Lancer le projet

### 1. Installer les dépendances (adapter selon votre système d'exploitation)


```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 2. Configurer la clé API Groq

Créer un fichier `.env` à la racine :

```
GROQ_API_KEY=votre_clé_ici
```

### 3. Télécharger les données

Télécharger le fichier `CIS_RCP.csv` depuis [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/base-de-donnees-publique-des-medicaments-base-officielle/) et le placer dans `data/`.

### 4. Créer l'index FAISS (une seule fois)

```bash
python3 indexation.py
```

Le script est **idempotent** : si l'index existe déjà, il ne fait rien. Pour forcer la réindexation, supprimez le dossier `index/`.

### 5. Lancer l'assistant

**En ligne de commande :**
```bash
python3 rag.py
```

**Interface web (Streamlit) :**
```bash
streamlit run app.py
```

---

## Architecture

```
PHASE 1 — INDEXATION 
  CIS_RCP.csv → filtrage → extraction HTML par section → chunking → embeddings → VectorDB (FAISS)

PHASE 2 — INTERROGATION 
  Question → enrichissement avec historique → embedding → VectorDB.retrieve() → LLM Groq → réponse
```

**Structure du projet :**
```
config.py       — paramètres centralisés (modèles, chemins, médicaments cibles)
vector_db.py    — classe VectorDB (crée ou charge l'index selon qu'il existe)
indexation.py   — pipeline data : chargement CSV → parsing HTML → chunking → VectorDB
rag.py          — classe RAG : recherche vectorielle + LLM + historique + clarifications
app.py          — interface Streamlit : chat interactif avec sources
context.txt     — prompt système du LLM 
```

**Fichiers générés :**
- `index/medicaments.index` — index FAISS (vecteurs)
- `index/chunks.json` — textes et métadonnées (même ordre que les vecteurs)

---

## Médicaments indexés

15 médicaments courants : Doliprane, Dafalgan, Efferalgan, Ibuprofène, Nurofen, Aspirine, Aspégic, Amoxicilline, Augmentin, Smecta, Imodium, Ventoline, Oméprazole, Metformine, Glucophage.

---

## Choix techniques

### Source de données
Fichier `CIS_RCP.csv` de la BDPM (option téléchargement direct). Chaque ligne contient le code CIS et la notice HTML complète d'un médicament. Le fichier est encodé en Latin-1 avec du contenu HTML en UTF-8 — une fonction de réparation d'encodage est appliquée au chargement.

### Filtrage des médicaments
Le nom du médicament est recherché uniquement dans la **section dénomination** du HTML (balise `RcpDenomination`), pas dans tout le document. Cela évite de sélectionner une notice qui mentionne le médicament cible dans ses interactions.

### Stratégie de chunking
Les notices HTML sont structurées en sections bien définies (`RcpIndicTherap`, `RcpPosoAdmin`, `RcpContreIndic`, `RcpEffetsIndesirables`...). On exploite ces ancres pour **couper par section en premier**, puis on applique un chunker à fenêtre glissante sur les sections trop longues.

- **Taille max** : 800 caractères — correspond à environ un paragraphe médical, assez ciblé pour la recherche vectorielle sans perdre le contexte
- **Overlap** : 100 caractères — évite de couper une phrase importante entre deux chunks

### Enrichissement des embeddings
Chaque chunk est préfixé par le nom du médicament et le titre de sa section avant l'embedding :

```
"DOLIPRANE 100 mg — Effets indésirables : Les effets indésirables les plus fréquents sont..."
```

Cela permet à la recherche vectorielle de trouver les bons chunks même quand la question utilise le nom du médicament sans le répéter dans le texte de la section.

### Métadonnées
Chaque chunk stocke : `medicament`, `code_cis`, `section`, `chunk_index`. La section permet au LLM de citer précisément la source ("selon la section Effets indésirables du Doliprane...").

### Classe VectorDB — idempotence
Le constructeur de `VectorDB` vérifie si l'index existe sur disque. Si oui, il le charge. Sinon, il le crée à partir des documents fournis. Cela garantit qu'on ne recrée jamais l'index inutilement.

### Modèle d'embedding
`paraphrase-multilingual-mpnet-base-v2` — modèle multilingue supportant le français, nécessaire car les notices BDPM sont en français.

### Index FAISS
`IndexFlatL2` — recherche exacte par distance euclidienne. Un score faible = vecteurs proches = bonne pertinence. L'index est sauvegardé sur disque et rechargé sans réindexation à chaque lancement.

### LLM
`llama-3.3-70b-versatile` via Groq. Température à 0.2 pour des réponses précises et factuelles. Le prompt système (dans `context.txt`) impose de citer les sources, de ne répondre qu'à partir du contexte fourni, et d'inclure l'avertissement médical dans chaque réponse.

### Historique de conversation
La classe `RAG` maintient un historique des échanges en mémoire pour la durée de la session. Cet historique est injecté dans chaque appel au LLM, ce qui lui permet de comprendre le contexte des questions de suivi. Il enrichit aussi la requête FAISS : si l'utilisateur dit "enfant de 6 ans" après "posologie doliprane", la recherche vectorielle reçoit les deux ensemble.

### Questions de clarification
Le LLM peut poser une question de clarification si la demande est vague (médicament non précisé, âge manquant pour une posologie...). Les sources ne sont affichées qu'après une vraie réponse médicale, pas après une question de clarification.

### Questions impliquant deux médicaments
Avec TOP_K=8, les chunks de plusieurs médicaments différents sont récupérés simultanément. Le LLM synthétise alors à partir des deux contextes.

---

## Questions de réflexion

**Q1. Stratégie de chunking**  
On découpe d'abord par section (structure HTML exploitée), puis on redécoupe les sections longues en chunks de 800 caractères avec 100 de chevauchement. Cette taille correspond à un paragraphe médical — assez précis pour la recherche, assez complet pour fournir du contexte au LLM.

**Q2. Exploitation de la structure**  
Oui — les ancres HTML (`RcpIndicTherap`, `RcpEffetsIndesirables`...) sont utilisées pour segmenter la notice avant le chunking. Chaque chunk contient donc une information thématiquement cohérente.

**Q3. Distinguer les chunks par type**  
Le champ `section` dans les métadonnées (`"Effets indésirables"`, `"Posologie et administration"`...) permet d'identifier le type d'information de chaque chunk. De plus, le chunk est préfixé par ce titre de section dans le texte embedé, ce qui oriente la recherche vectorielle.

**Q4. Questions sur deux médicaments**  
TOP_K=8 permet de capturer des chunks de plusieurs médicaments en une seule recherche. Le LLM synthétise ensuite à partir de tous les extraits fournis.

**Q5. Prompt système**  
Le prompt (dans `context.txt`) impose : (1) ne répondre qu'à partir du contexte, (2) citer le nom du médicament source, (3) poser une question de clarification si la demande est vague, (4) ne pas ajouter l'avertissement médical lors d'une question de clarification, (5) terminer chaque vraie réponse par l'avertissement médical obligatoire.