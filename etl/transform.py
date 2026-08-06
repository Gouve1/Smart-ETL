import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ETL_Transform")

# Raiz do projeto (smart-etl)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_brand_map() -> Dict[str, str]:
    """Carrega o dicionário de padronização de marcas O(1)."""
    taxonomy_path = os.path.join(BASE_DIR, "config", "taxonomy.json")
    if not os.path.exists(taxonomy_path):
        logger.warning(
            f"Taxonomia não encontrada em {taxonomy_path}. Mapeamento vazio."
        )
        return {}

    with open(taxonomy_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    brands_dict = data.get("brands", data)
    brand_map = {}

    for official_brand, aliases in brands_dict.items():
        if official_brand == "OEM / Unbranded":
            continue

        brand_map[official_brand.lower()] = official_brand
        if isinstance(aliases, list):
            for alias in aliases:
                brand_map[alias.lower()] = official_brand

    return brand_map


class ProductTransformer:

    def __init__(self, brand_map: Dict[str, str]):
        self.brand_map = brand_map

        if self.brand_map:
            # Ordena aliases do MAIOR para o MENOR comprimento (Longest Match First)
            sorted_aliases = sorted(
                self.brand_map.keys(), key=len, reverse=True
            )

            # Padrão Regex único com boundary estrito \b
            pattern = (
                r"\b(" + "|".join(re.escape(a) for a in sorted_aliases) + r")\b"
            )

            # Compilação única em C engine na memória
            self.brand_regex = re.compile(pattern, re.IGNORECASE)
        else:
            self.brand_regex = None

    def _clean_price(self, price_val: float, source: str) -> float:
        if price_val > 1000.0 and source == "amazon":
            return round(price_val / 100.0, 2)
        return round(price_val, 2)

    def _extract_brand(
        self, title: str, seller_name: Optional[str]
    ) -> Optional[str]:
        if not self.brand_regex:
            return None

        # 1. Busca no Título
        match = self.brand_regex.search(title)
        if match:
            matched_alias = match.group(1).lower()
            return self.brand_map.get(matched_alias)

        # 2. Busca no Nome do Vendedor (se não for genérico)
        if seller_name and seller_name.lower() not in [
            "amazon merchant",
            "aliexpress merchant",
        ]:
            match = self.brand_regex.search(seller_name)
            if match:
                matched_alias = match.group(1).lower()
                return self.brand_map.get(matched_alias)

        return None

    def _generate_product_hash(
        self, source: str, source_id: str, title: str
    ) -> str:
        if source_id:
            return f"{source}_{source_id}".lower()
        clean_title = "".join(e for e in title.lower() if e.isalnum())
        return hashlib.md5(
            f"{source}_{clean_title}".encode("utf-8")
        ).hexdigest()

    def transform(self, item: Dict[str, Any]) -> Dict[str, Any]:
        raw_title = str(
            item.get("title") or item.get("raw_title") or ""
        ).strip()
        source = str(item.get("source", "unknown")).lower()
        source_id = str(item.get("source_id", ""))
        category = str(item.get("category", "Unassigned")).strip()

        try:
            price = self._clean_price(float(item.get("price", 0.0)), source)
        except (ValueError, TypeError):
            price = 0.0

        try:
            rating = float(item.get("seller_rating", 0.0))
        except (ValueError, TypeError):
            rating = 0.0

        extracted_brand = self._extract_brand(
            raw_title, item.get("seller_name")
        )

        return {
            "product_id": self._generate_product_hash(
                source, source_id, raw_title
            ),
            "source": source,
            "source_id": source_id,
            "title": raw_title,
            "brand": extracted_brand or "OEM / Unbranded",
            "category": category,
            "price_eur": price,
            "currency": item.get("currency", "EUR"),
            "stock_status": item.get("stock_status", "UNKNOWN"),
            "seller_name": item.get("seller_name"),
            "seller_rating": rating,
            "extracted_at": item.get("extracted_at"),
            "transformed_at": datetime.now(timezone.utc).isoformat(),
        }


def run_pipeline():
    raw_dir = os.path.join(BASE_DIR, "data", "raw")
    if not os.path.exists(raw_dir):
        logger.error(f"Diretório data/raw não encontrado em: {raw_dir}")
        return

    raw_files = [
        os.path.join(raw_dir, f)
        for f in os.listdir(raw_dir)
        if f.startswith("raw_products_")
    ]

    if not raw_files:
        logger.error("Nenhum arquivo raw_products_*.json encontrado em data/raw!")
        return

    latest_file = max(raw_files, key=os.path.getctime)
    logger.info(f"Processando o arquivo bruto mais recente: {latest_file}")

    with open(latest_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    brand_map = load_brand_map()
    logger.info(f"Taxonomia carregada com {len(brand_map)} termos/aliases.")

    transformer = ProductTransformer(brand_map)
    transformed_data = [transformer.transform(item) for item in raw_data]

    output_dir = os.path.join(BASE_DIR, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"processed_products_{timestamp}.json"
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed_data, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Transformação concluída! {len(transformed_data)} itens persistidos em {output_path}"
    )


if __name__ == "__main__":
    run_pipeline()