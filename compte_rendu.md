# Compte-rendu technique — Assistant Médicaments RAG

---

## Choix techniques justifiés

### 1. FAISS plutôt que ChromaDB
On a choisi FAISS (`IndexFlatL2`) pour la base vectorielle car il ne nécessite pas de serveur externe, fonctionne entièrement en local et offre une recherche exacte par distance euclidienne. ChromaDB aurait simplifié la gestion de la persistance mais ajoute une dépendance plus lourde. FAISS est plus adapté à un projet pédagogique où la transparence du fonctionnement est importante.

### 2. `paraphrase-multilingual-mpnet-base-v2` comme modèle d'embedding
Les notices BDPM sont en français. Un modèle multilingue était donc indispensable. Ce modèle produit des vecteurs de dimension 768 et offre un bon compromis entre performance et légèreté (pas besoin de GPU).

### 3. Chunking par section HTML avant découpe par taille
La notice médicale est structurée avec des ancres HTML (`RcpEffetsIndesirables`, `RcpPosoAdmin`...). Couper d'abord par section garantit que chaque chunk contient une information thématiquement cohérente. Un chunking uniquement par taille aurait mélangé des informations de sections différentes dans un même chunk.

### 4. Enrichissement des embeddings par préfixage
Chaque chunk est préfixé par `"{medicament} — {section} : "` avant l'embedding. Sans ce préfixe, une requête "doliprane effets secondaires" pouvait retourner des chunks d'un autre médicament dont le texte était similaire mais ne concernait pas le Doliprane.

### 5. Filtrage dans la section dénomination uniquement
Rechercher le nom du médicament dans tout le HTML causait des erreurs : une notice d'Acarbose mentionnait "metformine" dans ses interactions, ce qui la faisait remonter pour une requête sur la metformine. Restreindre la recherche à la section `RcpDenomination` (600 caractères après l'ancre) a résolu ce problème.

### 6. Architecture orientée objet
Le code est organisé en deux classes principales : `VectorDB` (gestion de l'index FAISS) et `RAG` (gestion du LLM et de la conversation). Cette séparation permet de réutiliser `VectorDB` dans d'autres projets sans modifier la logique RAG.

### 7. Script idempotent
`indexation.py` vérifie si l'index existe avant de le reconstruire. Cela évite de relancer une indexation longue (chargement du CSV, calcul des embeddings) à chaque lancement du projet. Pour forcer la réindexation, il suffit de supprimer le dossier `index/`.

### 8. Historique de conversation et clarifications
Le LLM reçoit l'historique complet des échanges à chaque tour. Cela lui permet de poser des questions de clarification (âge du patient pour une posologie, médicament non précisé) et de tenir compte des réponses dans sa recherche. La requête FAISS est également enrichie avec les messages précédents de l'utilisateur.

### 9. `TOP_K=8` et seuil de score
TOP_K=8 permet de capturer des chunks de plusieurs médicaments en une seule recherche, utile pour les questions comparatives. Le seuil de score L2 à 5.5 distingue les résultats pertinents des résultats trop éloignés sémantiquement.

### 10. Prompt système externalisé dans `context.txt`
Le prompt LLM est stocké dans un fichier texte séparé. Cela permet de le modifier sans toucher au code Python, et de le versionner indépendamment.

---

## Difficultés rencontrées

### 1. Problème d'encodage Latin-1 / UTF-8
**Problème :** Le fichier CSV est encodé en Latin-1, mais le contenu HTML à l'intérieur est du UTF-8. Les caractères accentués (é, è, ç...) s'affichaient mal ou provoquaient des erreurs.

**Solution :** Lire le CSV en Latin-1, puis ré-encoder chaque cellule HTML en Latin-1 et la décoder en UTF-8. Ajout de `errors="ignore"` et `errors="replace"` pour gérer les cas impossibles à convertir.

---

### 2. Mauvais médicaments sélectionnés au filtrage
**Problème :** La recherche de "metformine" dans tout le HTML retournait la notice d'Acarbose (qui mentionne "metformine" dans sa section interactions). Même problème pour "ibuprofene" qui retournait Acéclofénac.

**Solution :** Restreindre la recherche au contenu des 600 caractères suivant l'ancre `RcpDenomination`, là où le nom officiel du médicament est systématiquement présent.

---

### 3. `extraire_denomination` retournait vide pour tous les médicaments
**Problème :** La fonction cherchait une classe CSS (`AmmDenomination`) qui n'existait pas dans toutes les notices. Les notices du Doliprane utilisent par exemple `AmmCorpsTexteGras`.

**Solution :** Abandonner la recherche par classe CSS. Chercher la chaîne `rcpdenomination` par position dans le texte brut et extraire les 600 caractères suivants, indépendamment de la classe CSS.

---

### 4. `extraire_nom_medicament` retournait "Inconnu"
**Problème :** La fonction récupérait le texte du parent de l'ancre, qui ne contenait que le titre de section et pas le nom du médicament.

**Solution :** Itérer sur les `next_siblings` de l'ancre pour trouver le premier élément contenant du texte pertinent.



### 5. "Inconnu" persistant pour Augmentin et Smecta
**Problème :** Leur nom était contenu dans une balise `<a name="_Toc...">` (signet interne). La condition d'arrêt de la boucle `next_siblings` se déclenchait sur ce signet, pensant avoir atteint une nouvelle section.

**Solution :** Changer la condition d'arrêt pour ne s'arrêter que sur les ancres dont le `name` commence par `"Rcp"` — les vraies sections médicales.

---

### 6. FAISS retournait toujours "résultat non pertinent"
**Problème :** Le seuil de score L2 était fixé à 2.0. Les scores réels des requêtes pertinentes se situaient entre 3.4 et 5.5 — tous rejetés.

**Solution :** Analyse empirique des scores retournés sur plusieurs requêtes. Seuil progressivement relevé à 5.5.

---

### 7. Mauvais médicament retourné par FAISS
**Problème :** Une requête "doliprane effets secondaires" retournait des chunks d'Aripiprazole car les chunks ne contenaient pas le nom du médicament dans leur texte — seul le contenu médical brut était embedé.

**Solution :** Préfixer chaque chunk avec `"{medicament} — {section} : "` avant l'embedding. La requête "doliprane" trouve désormais les chunks qui commencent par "DOLIPRANE".

