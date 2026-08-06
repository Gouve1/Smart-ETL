import json
import os
import sys
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List

from sqlalchemy import Column, DateTime, Date, Float, Numeric, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import declarative_base, relationship

# Importa a engine e a sessão prontas do seu config.py
from config import engine, SessionLocal, logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Base = declarative_base()

# ==========================================
# MAPEAMENTO ORM (Alinhado com o seu db.sql)
# ==========================================

class CategoryModel(Base):
    __tablename__ = "categories"

    category_id = Column(String, primary_key=True)  # UUID gerado no banco ou python
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ProductModel(Base):
    __tablename__ = "products"

    product_id = Column(String, primary_key=True)
    category_id = Column(String, ForeignKey("categories.category_id", ondelete="CASCADE"), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    brand = Column(String(100), nullable=False)
    model = Column(String(100))
    msrp_eur = Column("msrp_eur", Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ProductCrossMapping(Base):
    __tablename__ = "product_cross_mappings"

    mapping_id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    source_platform = Column(String(50), nullable=False)
    external_id = Column(String(100), nullable=False)
    product_url = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    snapshot_id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    source_platform = Column(String(50), nullable=False)
    price_eur = Column(Numeric(10, 2), nullable=False)
    shipping_cost_eur = Column(Numeric(10, 2), default=0.00)
    currency = Column(String(3), default="EUR")
    availability_status = Column(String(50))
    condition_type = Column(String(50), default="NEW")
    captured_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class SellerMetric(Base):
    __tablename__ = "seller_metrics"

    metric_id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    source_platform = Column(String(50), nullable=False)
    seller_name = Column(String(255))
    seller_rating = Column(Numeric(5, 2))
    total_offers_count = Column(Numeric, default=1)
    snapshot_date = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Schema relacional do banco verificado/criado com sucesso.")


def load_products_relational(session, products_data: List[Dict[str, Any]]) -> int:
    if not products_data:
        logger.warning("Nenhum produto para carregar.")
        return 0

    count = 0
    for item in products_data:
        # 1. Tratar Categoria (Garante que a categoria existe ou cria com base no slug/nome)
        category_name = item.get("category", "Unassigned")
        category_slug = category_name.lower().replace(" ", "-")
        
        # Verifica se a categoria já existe na sessão
        cat_obj = session.query(CategoryModel).filter_by(slug=category_slug).first()
        if not cat_obj:
            import uuid
            cat_obj = CategoryModel(
                category_id=str(uuid.uuid4()),
                name=category_name,
                slug=category_slug,
                description=f"Categoria gerada automaticamente para {category_name}"
            )
            session.add(cat_obj)
            session.flush() # Garante o ID para uso imediato

        # 2. Tratar Produto Canônico (products)
        # Usamos o product_id gerado no transform como base ou geramos um UUID consistente
        import uuid
        prod_id = item.get("product_id") # Ex: hash MD5 ou ID customizado
        
        product_obj = session.query(ProductModel).filter_by(product_id=prod_id).first()
        if not product_obj:
            product_obj = ProductModel(
                product_id=prod_id,
                category_id=cat_obj.category_id,
                canonical_name=item.get("title"),
                brand=item.get("brand", "OEM / Unbranded"),
                model=None,
                msrp_eur=item.get("price_eur")
            )
            session.add(product_obj)
            session.flush()
        else:
            # Atualiza dados básicos se necessário
            product_obj.canonical_name = item.get("title")
            product_obj.brand = item.get("brand", "OEM / Unbranded")
            session.flush()

        # 3. Tratar Mapeamento de Cross-Platform (product_cross_mappings)
        source_platform = item.get("source", "unknown")
        external_id = item.get("source_id") or prod_id
        
        mapping_obj = session.query(ProductCrossMapping).filter_by(
            source_platform=source_platform, external_id=external_id
        ).first()
        
        if not mapping_obj:
            mapping_obj = ProductCrossMapping(
                mapping_id=str(uuid.uuid4()),
                product_id=product_obj.product_id,
                source_platform=source_platform,
                external_id=external_id,
                product_url=item.get("product_url")
            )
            session.add(mapping_obj)

        # 4. Inserir Snapshot de Preço (Time-series)
        price_snapshot = PriceSnapshot(
            snapshot_id=str(uuid.uuid4()),
            product_id=product_obj.product_id,
            source_platform=source_platform,
            price_eur=item.get("price_eur", 0.0),
            shipping_cost_eur=0.00,
            currency=item.get("currency", "EUR"),
            availability_status=item.get("stock_status", "UNKNOWN"),
            condition_type="NEW",
            captured_at=datetime.now(timezone.utc)
        )
        session.add(price_snapshot)

        # 5. Inserir Métricas do Vendedor (seller_metrics)
        seller_metric = SellerMetric(
            metric_id=str(uuid.uuid4()),
            product_id=product_obj.product_id,
            source_platform=source_platform,
            seller_name=item.get("seller_name"),
            seller_rating=item.get("seller_rating", 0.0),
            total_offers_count=1,
            snapshot_date=datetime.now(timezone.utc).date()
        )
        session.add(seller_metric)

        count += 1

    session.commit()
    return count


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
        count = load_products_relational(session, data)
        logger.info(f"Sucesso! {count} registros processados e distribuídos nas tabelas relacionais do PostgreSQL.")
    except Exception as e:
        session.rollback()
        logger.error(f"Erro na carga relacional do banco: {e}", exc_info=True)
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    run_loader()