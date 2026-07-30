import json
import logging
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

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
logger = logging.getLogger("ETL_Extract")

load_dotenv()

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": ""
}

def extract_amazon_eu(query="Mechanical Keyboard"):
    if not RAPIDAPI_KEY:
        logger.error("RAPIDAPI_KEY não encontrada no arquivo .env!")
        return []

    logger.info(f"Buscando '{query}' na Amazon EU via RapidAPI...")
    url = "https://real-time-amazon-data.p.rapidapi.com/search"
    
    headers = HEADERS.copy()
    headers["X-RapidAPI-Host"] = "real-time-amazon-data.p.rapidapi.com"
    params = {"query": query, "country": "DE"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()
        
        extracted = []
        products = data.get("data", {}).get("products", [])
        
        for item in products[:5]: 
            price_raw = item.get("product_price") or "0"
            clean_price = float(price_raw.replace("€", "").replace("$", "").replace(",", "").strip() or 0.0)
            
            extracted.append({
                "source": "amazon",
                "source_id": item.get("asin"),
                "title": item.get("product_title"),
                "price": clean_price, # Será normalizado (/100) no transform.py
                "currency": "EUR",
                "seller_name": "Amazon Merchant",
                "seller_rating": float(item.get("product_star_rating") or 0.0),
                "stock_status": "In Stock" if not item.get("is_out_of_stock") else "Out of Stock",
                "extracted_at": datetime.now(timezone.utc).isoformat()
            })
        logger.info(f"Amazon EU: {len(extracted)} itens obtidos com sucesso.")
        return extracted

    except requests.exceptions.RequestException as e:
        logger.error(f"Falha na requisição da Amazon: {e}")
        return []

def extract_aliexpress_eu(query="Mechanical Keyboard"):
    """
    Extrai produtos do AliExpress DE usando a AliExpress Business API via RapidAPI.
    """
    if not RAPIDAPI_KEY:
        logger.error("RAPIDAPI_KEY não encontrada no arquivo .env!")
        return []

    logger.info(f"Buscando '{query}' no AliExpress DE (Ao vivo)...")
    url = "https://aliexpress-business-api.p.rapidapi.com/textsearch.php"
    
    # Headers completos validados via engenharia reversa do console RapidAPI
    headers = {
        "accept": "application/json",
        "rapid-client": "hub-service",
        "x-rapidapi-host": "aliexpress-business-api.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-ua": "RapidAPI-Playground",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }

    params = {
        "keyWord": query,
        "pageSize": "10",
        "pageIndex": "1",
        "country": "DE",
        "currency": "EUR",
        "lang": "en",
        "filter": "orders",
        "sortBy": "asc"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("data", {}).get("itemList", [])
        extracted = []

        for item in items[:5]:
            item_id = item.get("itemId")
            title = item.get("title")
            
            # Captura de preço dinâmico em EUR (prioriza targetSalePrice ou salePrice)
            price_val = (
                item.get("targetSalePrice") or 
                item.get("salePrice") or 
                item.get("originalPrice") or 
                0.0
            )

            rating = item.get("score") or 0.0

            if item_id and title:
                extracted.append({
                    "source": "aliexpress",
                    "source_id": str(item_id),
                    "title": str(title).strip(),
                    "price": float(price_val),
                    "currency": "EUR",
                    "seller_name": "AliExpress Merchant",
                    "seller_rating": float(rating) if rating != "" else 0.0,
                    "stock_status": "In Stock",
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
            
        logger.info(f"AliExpress: {len(extracted)} produtos reais extraídos com sucesso.")
        return extracted

    except Exception as e:
        logger.error(f"Erro na extração ao vivo do AliExpress: {e}")
        return []

def run_extraction(search_term="Mechanical Keyboard"):
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    
    all_data = []
    all_data.extend(extract_amazon_eu(search_term))
    all_data.extend(extract_aliexpress_eu(search_term))
    
    if not all_data:
        logger.warning("Nenhum dado foi extraído de nenhuma das fontes.")
        return []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(RAW_DATA_DIR, f"raw_products_{timestamp}.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
        
    logger.info(f"Snapshot salvo em {file_path} com {len(all_data)} registros no total.")
    return all_data

if __name__ == "__main__":
    run_extraction()