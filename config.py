EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"
GROQ_MODEL = "llama-3.3-70b-versatile"
TOP_K = 8
SEUIL_SCORE = 5.5
INDEX_DIR = "index"
DATA_PATH = "data/CIS_RCP.csv"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
PROMPT_PATH = "context.txt"

MEDICAMENTS_CIBLES = [
    "doliprane",
    "dafalgan",
    "efferalgan",
    "ibuprofene",
    "nurofen",
    "aspirine",
    "aspegic",
    "amoxicilline",
    "augmentin",
    "smecta",
    "imodium",
    "ventoline",
    "omeprazole",
    "metformine",
    "glucophage",
]

SECTIONS_UTILES = {
    "RcpDenomination": "Dénomination",
    "RcpIndicTherap": "Indications thérapeutiques",
    "RcpPosoAdmin": "Posologie et administration",
    "RcpContreIndic": "Contre-indications",
    "RcpMisesEnGarde": "Mises en garde",
    "RcpInteractions": "Interactions médicamenteuses",
    "RcpEffetsIndesirables": "Effets indésirables",
    "RcpGrossAllait": "Grossesse et allaitement",
    "RcpSurdosage": "Surdosage",
}
