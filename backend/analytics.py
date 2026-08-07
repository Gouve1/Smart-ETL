import logging
import pandas as pd
from typing import Dict, Any, Optional
from sqlalchemy import text
from etl.config import engine

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AI_Analytics")


def get_pricing_intelligence(product_id: str) -> Optional[Dict[str, Any]]:
    """
    Extracts deep pricing intelligence, competitor gap, and stock-out status 
    for a given product to feed the AI Copilot.
    """
    query = """
    WITH latest_market_data AS (
        SELECT DISTINCT ON (ps.source_platform)
            ps.product_id,
            ps.source_platform,
            ps.price_eur,
            ps.shipping_cost_eur,
            (ps.price_eur + COALESCE(ps.shipping_cost_eur, 0)) AS total_cost_eur,
            ps.availability_status,
            ps.captured_at,
            sm.seller_name,
            sm.seller_rating
        FROM price_snapshots ps
        LEFT JOIN LATERAL (
            SELECT seller_name, seller_rating
            FROM seller_metrics
            WHERE product_id = ps.product_id 
              AND source_platform = ps.source_platform
            ORDER BY snapshot_date DESC
            LIMIT 1
        ) sm ON true
        WHERE ps.product_id = :target_product_id
        ORDER BY ps.source_platform, ps.captured_at DESC
    ),
    market_benchmarks AS (
        SELECT 
            MIN(total_cost_eur) FILTER (WHERE availability_status ILIKE '%in stock%') AS min_in_stock_price,
            MIN(total_cost_eur) AS absolute_min_price
        FROM latest_market_data
    )
    SELECT 
        p.product_id,
        p.canonical_name,
        p.brand,
        p.msrp_eur AS our_reference_price,
        lmd.source_platform,
        lmd.total_cost_eur,
        lmd.availability_status,
        lmd.seller_rating,
        mb.min_in_stock_price,
        CASE 
            WHEN mb.min_in_stock_price > 0 THEN 
                ROUND(((lmd.total_cost_eur - mb.min_in_stock_price) / mb.min_in_stock_price) * 100, 2)
            ELSE 0.0
        END AS gap_to_market_min_pct,
        CASE 
            WHEN lmd.availability_status NOT ILIKE '%in stock%' THEN 'OPPORTUNITY: Competitor Out of Stock'
            WHEN lmd.total_cost_eur = mb.min_in_stock_price THEN 'BUY BOX / LEADER'
            ELSE 'TRAILING'
        END AS market_position_status
    FROM products p
    CROSS JOIN market_benchmarks mb
    JOIN latest_market_data lmd ON p.product_id = lmd.product_id
    WHERE p.product_id = :target_product_id;
    """

    try:
        # Executa de forma segura usando conexão explícita do SQLAlchemy com suporte total a dicionários
        with engine.connect() as connection:
            result = connection.execute(text(query), {"target_product_id": product_id})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if df.empty:
            logger.warning(f"No analytics data found for product_id: {product_id}")
            return None

        # Structure the payload cleanly for the LLM context
        product_info = {
            "product_id": df["product_id"].iloc[0],
            "canonical_name": df["canonical_name"].iloc[0],
            "brand": df["brand"].iloc[0],
            "our_reference_price_eur": float(df["our_reference_price"].iloc[0]) if pd.notna(df["our_reference_price"].iloc[0]) else None,
            "market_min_in_stock_eur": float(df["min_in_stock_price"].iloc[0]) if pd.notna(df["min_in_stock_price"].iloc[0]) else None,
            "competitors_landscape": []
        }

        for _, row in df.iterrows():
            product_info["competitors_landscape"].append({
                "platform": row["source_platform"],
                "total_price_eur": float(row["total_cost_eur"]),
                "availability": row["availability_status"],
                "seller_rating": float(row["seller_rating"]) if pd.notna(row["seller_rating"]) else 0.0,
                "gap_to_lowest_pct": float(row["gap_to_market_min_pct"]),
                "strategic_status": row["market_position_status"]
            })

        logger.info(f"Analytics successfully compiled for: {product_info['canonical_name']}")
        return product_info

    except Exception as e:
        logger.error(f"Error fetching pricing intelligence for {product_id}: {e}", exc_info=True)
        return None