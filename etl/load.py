import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import Column, DateTime, Float, Numeric, String, Text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import declarative_base

# Importa a engine e a sessão prontas do seu config.py
from config import engine, SessionLocal, logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Base = declarative_base()

class Product(Base):
    __tablename__ = "dim_products"

    product_id = Column(String(64), primary_key=True)
    source = Column(String(32), nullable=False, index=True)
    source_id = Column(String(128), nullable=True)
    title = Column(Text, nullable=False)
    brand = Column(String(64), nullable=False, index=True)
    price_eur = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default="EUR")
    stock_status = Column(String(32), default="UNKNOWN")
    seller_name = Column(String(128), nullable=True)
    seller_rating = Column(Float, default=0.0)
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    transformed_at = Column(DateTime(timezone=True), nullable=True)
    loaded_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Schema do banco verificado/criado com sucesso.")

def upsert_products(session, products_data: List[Dict[str, Any]]) -> int:
    if not products_data:
        logger.warning("Nenhum produto para carregar.")
        return 0

    stmt = insert(Product).values(products_data)
    update_cols = {
        "title": stmt.excluded.title,
        "brand": stmt.excluded.brand,
        "price_eur": stmt.excluded.price_eur,
        "currency": stmt.excluded.currency,
        "stock_status": stmt.excluded.stock_status,
        "seller_name": stmt.excluded.seller_name,
        "seller_rating": stmt.excluded.seller_rating,
        "transformed_at": stmt.excluded.transformed_at,
        "loaded_at": datetime.now(timezone.utc),
    }

    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["product_id"], set_=update_cols
    )

    session.execute(upsert_stmt)
    session.commit()
    return len(products_data)

def run_loader():
    processed_dir = os.path.join(BASE_DIR, "data", "processed")
    if not os.path.exists(processed_dir):
        logger.error(f"Diretório {processed_dir} não encontrado.")
        return

    processed_files = [
        os.path.join(processed_dir, f)
        for f in os.listdir(processed_dir)
        if f.startswith("processed_products_")
    ]

    if not processed_files:
        logger.error("Nenhum arquivo processado encontrado em data/processed!")
        return

    latest_file = max(processed_files, key=os.path.getctime)
    logger.info(f"Lendo o arquivo processado mais recente: {latest_file}")

    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    init_db()
    session = SessionLocal()

    try:
        count = upsert_products(session, data)
        logger.info(f"Sucesso! {count} produtos upsertados no PostgreSQL.")
    except Exception as e:
        session.rollback()
        logger.error(f"Erro na carga do banco: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    run_loader()