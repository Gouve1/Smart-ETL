-- database/db.sql
-- MarketIntelligence - Multi-Source E-Commerce Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Categorias Monitoradas (ex: Consoles, Laptops, Audio)
CREATE TABLE categories (
    category_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Produtos Canônicos (O produto "mestre" que unifica os mercados)
-- Ex: "Sony PlayStation 5 Slim", "Apple MacBook Air M2 8GB/256GB"
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID NOT NULL REFERENCES categories(category_id) ON DELETE CASCADE,
    canonical_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100),
    msrp_usd DECIMAL(10, 2), -- Preço sugerido pelo fabricante
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Mapeamento de IDs nas Fontes/APIs (Cross-Matching)
-- Relaciona o produto mestre com o ID único de cada marketplace
CREATE TABLE product_cross_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL, -- 'AMAZON', 'EBAY', 'BESTBUY'
    external_id VARCHAR(100) NOT NULL,   -- ASIN da Amazon, ItemID do eBay, SKU da Best Buy
    product_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_platform_external UNIQUE (source_platform, external_id)
);

-- 4. Histórico Temporal de Preços (Time-Series Table)
-- Onde o ETL grava os snapshots de preços capturados diariamente de cada API
CREATE TABLE price_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL, -- 'AMAZON', 'EBAY', 'BESTBUY'
    price_usd DECIMAL(10, 2) NOT NULL,
    shipping_cost_usd DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    availability_status VARCHAR(50),      -- 'IN_STOCK', 'OUT_OF_STOCK', 'LIMITED'
    condition_type VARCHAR(50) DEFAULT 'NEW', -- 'NEW', 'REFURBISHED', 'USED'
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Métricas de Vendedores e Ofertas (Market Share por Loja)
-- Consolida a reputação e a quantidade de ofertas daquele produto em cada loja
CREATE TABLE seller_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL,
    seller_name VARCHAR(255),
    seller_rating DECIMAL(3, 2),          -- ex: 4.85 / 5.00
    total_offers_count INT DEFAULT 1,     -- Quantidade de vendedores oferecendo o mesmo item
    snapshot_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- ÍNDICES DE ALTA PERFORMANCE (Essenciais para consultas rápidas no Dashboard)
-- ============================================================================

-- Acelera busca de histórico de preços por produto e data
CREATE INDEX idx_price_snapshots_lookup 
ON price_snapshots(product_id, captured_at DESC);

-- Acelera comparações de preço agrupadas por plataforma
CREATE INDEX idx_price_snapshots_platform 
ON price_snapshots(source_platform, captured_at);

-- Acelera o cruzamento das APIs no ETL
CREATE INDEX idx_cross_mappings_lookup 
ON product_cross_mappings(source_platform, external_id);