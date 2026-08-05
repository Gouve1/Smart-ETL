import os
import json
import re
import logging
from datetime import datetime
from rapidfuzz import process, fuzz

# Setup de Logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ETL_Transform")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_PATH = os.path.join(BASE_DIR, "config", "taxonomy.json")

# 1. Carregamento da Taxonomia Externa
def load_taxonomy():
    if not os.path.exists(TAXONOMY_PATH):
        logger.error(f"Arquivo de taxonomia não encontrado em: {TAXONOMY_PATH}")
        raise FileNotFoundError(f"Taxonomy file missing: {TAXONOMY_PATH}")
    
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    master_brands = data.get("master_brands", [])
    stopwords = set(data.get("category_stopwords", []))
    
    # Dicionário Mestre de Busca O(1): { "ajazz": "Ajazz", "aula": "AULA", "logitech": "Logitech" }
    brand_map = {b.lower(): b for b in master_brands}
    
    return master_brands, brand_map, stopwords

MASTER_BRANDS, BRAND_MAP, CATEGORY_STOPWORDS = load_taxonomy()


# 2. Resolução de Entidades (Brand Resolution Engine)
def resolve_brand(title: str, seller_name: str = "", raw_brand: str = "") -> str:
    """
    Resolução Determinística de Marcas Escalável:
    Camada 1: Metadados explícitos (raw_brand / seller_name) via BRAND_MAP ou RapidFuzz.
    Camada 2: Intersecção de Tokens O(1) em minúsculas (Insensível a Maiúsculas/Minúsculas).
    Camada 3: Fuzzy Matching sintático com RapidFuzz (Typos no título).
    Camada 4: Fallback estrito para OEM / Unbranded.
    """
    # Camada 1: Checagem de Metadados Explícitos
    for candidate in [raw_brand, seller_name]:
        if candidate:
            cand_clean = candidate.strip().lower()
            if cand_clean in BRAND_MAP:
                return BRAND_MAP[cand_clean]
            
            # Match aproximado nos metadados
            match = process.extractOne(candidate, MASTER_BRANDS, scorer=fuzz.partial_ratio, score_cutoff=85)
            if match:
                return match[0]

    if not title:
        return "OEM / Unbranded"

    # Preparação dos tokens do título (limpeza de caracteres especiais)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).lower()
    title_tokens = set(clean_title.split())

    # Camada 2: Intersecção de Sets O(1) insensível à caixa (Ex: "ajazz", "AULA", "Rk")
    matched_brand_keys = title_tokens.intersection(BRAND_MAP.keys())
    if matched_brand_keys:
        # Pega a primeira correspondência e retorna a marca oficial formatada do taxonomia.json
        matched_key = next(iter(matched_brand_keys))
        return BRAND_MAP[matched_key]

    # Camada 3: Fuzzy Match com RapidFuzz em tokens limpos sem stopwords (Tratamento de Typos)
    filtered_tokens = [w for w in clean_title.split() if w not in CATEGORY_STOPWORDS]
    if filtered_tokens:
        candidate_string = " ".join(filtered_tokens[:3])
        match = process.extractOne(candidate_string, MASTER_BRANDS, scorer=fuzz.partial_ratio, score_cutoff=80)
        if match:
            return match[0]

    # Camada 4: Classificação defensiva para catálogo não catalogado
    return "OEM / Unbranded"


# 3. Gerador de Chave Canônica Determinística
def generate_canonical_key(brand: str, title: str) -> str:
    """
    Normaliza o título para gerar uma chave única de agrupamento de produtos.
    """
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', title).lower()
    words = [w for w in clean.split() if w not in CATEGORY_STOPWORDS]
    
    # Remove o nome da marca da string do modelo para evitar redundância
    brand_lower = brand.lower()
    words = [w for w in words if w != brand_lower]
    
    model_slug = "-".join(words[:4])
    brand_slug = re.sub(r'[^a-zA-Z0-9]', '', brand).lower()
    
    return f"{brand_slug}-{model_slug}" if model_slug else brand_slug


# 4. Pipeline Principal de Transformação
def transform_raw_data(raw_file_path: str):
    if not os.path.exists(raw_file_path):
        logger.error(f"Arquivo bruto não encontrado: {raw_file_path}")
        return

    with open(raw_file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    logger.info(f"Iniciando transformação de {len(raw_data)} itens...")
    transformed_products = []

    for item in raw_data:
        title = item.get("title", "")
        seller = item.get("seller_name", "")
        raw_brand = item.get("raw_brand", "")

        # Resolução escalável de marca
        resolved_brand = resolve_brand(title=title, seller_name=seller, raw_brand=raw_brand)
        canonical_key = generate_canonical_key(resolved_brand, title)

        transformed_item = {
            "source": item.get("source", "unknown"),
            "source_id": item.get("source_id"),
            "raw_title": title,
            "title": title.strip(),
            "brand": resolved_brand,
            "canonical_key": canonical_key,
            "price_eur": float(item.get("price_eur", 0.0)),
            "stock_status": item.get("stock_status", "IN_STOCK"),
            "seller_name": seller,
            "seller_rating": float(item.get("seller_rating", 0.0)),
            "extracted_at": item.get("extracted_at"),
            "transformed_at": datetime.utcnow().isoformat()
        }
        transformed_products.append(transformed_item)

    # Salvando os dados processados
    output_dir = os.path.join(BASE_DIR, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"processed_products_{timestamp}.json"
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed_products, f, indent=2, ensure_ascii=False)

    logger.info(f"Dados salvos com sucesso em: {output_path}")
    return output_path


def run_transform():
    raw_dir = os.path.join(BASE_DIR, "data", "raw")
    if not os.path.exists(raw_dir):
        logger.error("Diretório data/raw não encontrado!")
        return

    raw_files = [os.path.join(raw_dir, f) for f in os.listdir(raw_dir) if f.startswith("raw_products_")]
    if not raw_files:
        logger.error("Nenhum arquivo raw_products_*.json encontrado!")
        return

    latest_file = max(raw_files, key=os.path.getctime)
    logger.info(f"Processando o arquivo mais recente: {latest_file}")
    transform_raw_data(latest_file)


if __name__ == "__main__":
    run_transform()