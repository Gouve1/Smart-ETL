import json
import logging
import os
import re
from datetime import datetime, timezone

# Configuração do Logger
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

PROCESSED_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

def clean_string(text: str) -> str:
    """Sanitiza strings removendo quebras de linha e espaços duplos."""
    if not text:
        return ""
    return " ".join(str(text).strip().split())

def normalize_price(price, source: str) -> float:
    """Trata conversões de preços e edge cases de tipos de dados."""
    if price is None:
        return 0.0
    try:
        val = float(price)
        # Ajuste de escala da Amazon caso venha em centavos (> 1000)
        if source.lower() == "amazon" and val > 1000:
            val = val / 100.0
        return round(val, 2)
    except (ValueError, TypeError):
        return 0.0

def extract_brand(title: str) -> str:
    """Extrai a marca principal do título via Regex."""
    brands = ["Logitech", "Razer", "Corsair", "Redragon", "Keychron", "SteelSeries", "HyperX", "EPOMAKER", "RK ROYAL KLUDGE"]
    for brand in brands:
        if re.search(r'\b' + re.escape(brand) + r'\b', title, re.IGNORECASE):
            return brand
    return "Generic / Unbranded"

def generate_canonical_key(title: str, brand: str) -> str:
    """Cria um identificador canônico simplificado para agrupar produtos idênticos."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', title).lower()
    words = clean.split()[:4]  # Pega as 4 primeiras palavras-chave significativas
    return f"{brand.lower()}-" + "-".join(words)

def transform_raw_payload(raw_data: list) -> list:
    logger.info(f"Iniciando transformação avançada de {len(raw_data)} registros brutos...")
    transformed = []
    discarded_count = 0

    for idx, item in enumerate(raw_data):
        source = item.get("source", "unknown").upper() # 'AMAZON' ou 'ALIEXPRESS'
        raw_price = item.get("price")
        
        price_eur = normalize_price(raw_price, source)
        clean_title = clean_string(item.get("title", ""))

        # Regra de Negócio: Filtro de integridade estrita
        if not clean_title or price_eur <= 0.0:
            discarded_count += 1
            logger.warning(
                f"Item #{idx + 1} descartado ({source}): "
                f"ID={item.get('source_id')} | Preço={raw_price} | Título Vazio={not clean_title}"
            )
            continue

        brand = extract_brand(clean_title)
        canonical_key = generate_canonical_key(clean_title, brand)

        transformed_item = {
            "source": source,
            "source_id": str(item.get("source_id")),
            "title": clean_title,
            "brand": brand,
            "canonical_key": canonical_key,
            "price_eur": price_eur,
            "currency": "EUR",
            "seller_name": item.get("seller_name", f"{source.capitalize()} Merchant"),
            "seller_rating": float(item.get("seller_rating") or 0.0),
            "stock_status": item.get("stock_status", "IN_STOCK"),
            "extracted_at": item.get("extracted_at"),
            "transformed_at": datetime.now(timezone.utc).isoformat()
        }
        transformed.append(transformed_item)

    logger.info(f"Transformação concluída: {len(transformed)} validados | {discarded_count} descartados.")
    return transformed

def run_transformation():
    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    if not os.path.exists(raw_dir):
        logger.error("Diretório data/raw não encontrado!")
        return []

    raw_files = [os.path.join(raw_dir, f) for f in os.listdir(raw_dir) if f.startswith("raw_products_")]
    if not raw_files:
        logger.error("Nenhum arquivo raw_products_*.json encontrado!")
        return []

    latest_raw_file = max(raw_files, key=os.path.getctime)
    logger.info(f"Lendo dados brutos de: {latest_raw_file}")

    with open(latest_raw_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    clean_data = transform_raw_payload(raw_data)

    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(PROCESSED_DATA_DIR, f"processed_products_{timestamp}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, indent=4, ensure_ascii=False)

    logger.info(f"Dados salvos com sucesso em: {output_path}")
    return clean_data

if __name__ == "__main__":
    run_transformation()