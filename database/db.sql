-- database/db.sql
-- MarketIntelligence - Multi-Source E-Commerce Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Monitored Categories
CREATE TABLE categories (
    category_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Canonical Products
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID NOT NULL REFERENCES categories(category_id) ON DELETE CASCADE,
    canonical_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100),
    msrp_eur DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Source/API Identifiers Mapping (Cross-Matching)
CREATE TABLE product_cross_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL, 
    external_id VARCHAR(100) NOT NULL,   -- Amazon ASIN, AliExpress ItemID
    product_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_platform_external UNIQUE (source_platform, external_id)
);

-- 4. Historical Price Snapshots (Time-Series Table)
CREATE TABLE price_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL,
    price_eur DECIMAL(10, 2) NOT NULL,
    shipping_cost_eur DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'EUR',
    availability_status VARCHAR(50),      -- 'IN_STOCK', 'OUT_OF_STOCK'
    condition_type VARCHAR(50) DEFAULT 'NEW',
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Seller Metrics & Offers
CREATE TABLE seller_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL,
    seller_name VARCHAR(255),
    seller_rating DECIMAL(5, 2),
    total_offers_count INT DEFAULT 1,
    snapshot_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- INDEXES
CREATE INDEX idx_price_snapshots_lookup ON price_snapshots(product_id, captured_at DESC);
CREATE INDEX idx_price_snapshots_platform ON price_snapshots(source_platform, captured_at);
CREATE INDEX idx_cross_mappings_lookup ON product_cross_mappings(source_platform, external_id);