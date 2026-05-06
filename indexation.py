import os
import re
import pandas as pd
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

from config import DATA_PATH, INDEX_DIR, CHUNK_SIZE, CHUNK_OVERLAP, MEDICAMENTS_CIBLES, SECTIONS_UTILES
from vector_db import VectorDB

load_dotenv()


# --- Bloc 1 : Chargement et filtrage des données ---

def reparer_encodage(texte) -> str:
    if not isinstance(texte, str):
        return ""
    try:
        return texte.encode("latin-1", errors="ignore").decode("utf-8", errors="replace")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texte


def charger_donnees(chemin: str) -> pd.DataFrame:
    print("Chargement du fichier CSV...")
    df = pd.read_csv(chemin, sep="\t", encoding="latin-1")
    df["RCP_html"] = df["RCP_html"].apply(reparer_encodage)
    print(f"  {len(df)} notices chargées au total")
    return df


def extraire_denomination(html: str) -> str:
    if not isinstance(html, str):
        return ""
    idx = html.lower().find("rcpdenomination")
    if idx < 0:
        return ""
    extrait = html[idx: idx + 600]
    texte = re.sub(r"<[^>]+>", " ", extrait)
    return re.sub(r"\s+", " ", texte).strip().lower()


def filtrer_medicaments(df: pd.DataFrame, noms: list) -> pd.DataFrame:
    print("Filtrage des médicaments cibles...")
    denominations = df["RCP_html"].apply(extraire_denomination)

    lignes_selectionnees = []
    for nom in noms:
        pattern = r"\b" + re.escape(nom) + r"\b"
        masque = denominations.str.contains(pattern, regex=True, na=False)
        correspondances = df[masque]
        if len(correspondances) == 0:
            print(f"  ATTENTION : '{nom}' introuvable dans la base")
            continue
        lignes_selectionnees.append(correspondances.iloc[0])
        print(f"  '{nom}' : notice trouvée (Code CIS: {correspondances.iloc[0]['Code_CIS']})")

    resultat = pd.DataFrame(lignes_selectionnees).reset_index(drop=True)
    print(f"  {len(resultat)} notices sélectionnées au total")
    return resultat


# --- Bloc 2 : Extraction du texte depuis le HTML ---

def extraire_nom_medicament(soup: BeautifulSoup) -> str:
    ancre = soup.find("a", {"name": "RcpDenomination"})
    if not ancre:
        return "Inconnu"
    for element in ancre.parent.next_siblings:
        if not isinstance(element, Tag):
            continue
        ancre_section = element.find("a", attrs={"name": lambda n: n and n.startswith("Rcp")})
        if ancre_section:
            break
        texte = element.get_text(separator=" ", strip=True)
        if texte:
            return texte
    return "Inconnu"


def extraire_section(soup: BeautifulSoup, nom_ancre: str) -> str:
    balise = soup.find("a", {"name": nom_ancre})
    if not balise:
        return ""

    textes = []
    for element in balise.parent.next_siblings:
        if element.name and element.find("a", href="#HautDePage"):
            break
        if hasattr(element, "get_text"):
            texte = element.get_text(separator=" ", strip=True)
            if texte:
                textes.append(texte)

    return " ".join(textes)


def html_vers_sections(html: str, code_cis: int) -> list:
    soup = BeautifulSoup(html, "html.parser")
    nom = extraire_nom_medicament(soup)
    sections = []

    for ancre, titre_section in SECTIONS_UTILES.items():
        texte = extraire_section(soup, ancre)
        if not texte or len(texte) < 20:
            continue
        texte = re.sub(r"\s+", " ", texte).strip()
        sections.append({
            "medicament": nom,
            "code_cis": code_cis,
            "section": titre_section,
            "texte": texte,
        })

    return sections


def extraire_toutes_sections(df: pd.DataFrame) -> list:
    print("Extraction du texte des notices...")
    toutes_sections = []
    for _, ligne in df.iterrows():
        sections = html_vers_sections(ligne["RCP_html"], ligne["Code_CIS"])
        toutes_sections.extend(sections)
    print(f"  {len(toutes_sections)} sections extraites")
    return toutes_sections


# --- Bloc 3 : Chunking ---

def chunker(texte: str, taille_max: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    if len(texte) <= taille_max:
        return [texte]

    chunks = []
    debut = 0
    while debut < len(texte):
        fin = debut + taille_max
        if fin < len(texte):
            dernier_espace = texte.rfind(" ", debut, fin)
            if dernier_espace > debut:
                fin = dernier_espace
        chunks.append(texte[debut:fin].strip())
        debut = fin - overlap

    return chunks


def creer_documents(sections: list) -> list:
    print("Découpage en chunks...")
    documents = []
    for i, section in enumerate(sections):
        chunks = chunker(section["texte"])
        for j, chunk in enumerate(chunks):
            contenu_enrichi = f"{section['medicament']} — {section['section']} : {chunk}"
            documents.append({
                "id": f"doc_{i:04d}_chunk_{j:02d}",
                "contenu": contenu_enrichi,
                "metadata": {
                    "medicament": section["medicament"],
                    "code_cis": section["code_cis"],
                    "section": section["section"],
                    "chunk_index": j,
                    "total_chunks": len(chunks),
                }
            })
    print(f"  {len(documents)} chunks créés")
    return documents


# --- Main ---

def main():
    print("=" * 50)
    print("  PHASE 1 : INDEXATION")
    print("=" * 50)

    # Idempotence : si l'index existe déjà, on ne refait rien
    index_path = os.path.join(INDEX_DIR, "medicaments.index")
    if os.path.exists(index_path):
        print("Index déjà existant. Rien à faire.")
        print("Pour forcer la réindexation, supprimez le dossier 'index/'.")
        return

    df = charger_donnees(DATA_PATH)
    df_filtre = filtrer_medicaments(df, MEDICAMENTS_CIBLES)
    sections = extraire_toutes_sections(df_filtre)
    documents = creer_documents(sections)

    VectorDB(INDEX_DIR, documents=documents)

    print("=" * 50)
    print("  Indexation terminée avec succès !")
    print(f"  {len(documents)} chunks indexés pour {len(df_filtre)} médicaments")
    print("=" * 50)


if __name__ == "__main__":
    main()
