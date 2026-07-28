-- database/db.sql
-- MarketIntelligence - Multi-Source E-Commerce Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Monitored Categories (e.g., Gaming Consoles, Laptops, Audio)
CREATE TABLE categories (
    category_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Canonical Products (Master product entity unifying cross-platform items)
-- e.g., "Sony PlayStation 5 Slim", "Apple MacBook Air M2 8GB/256GB"
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID NOT NULL REFERENCES categories(category_id) ON DELETE CASCADE,
    canonical_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100),
    msrp_usd DECIMAL(10, 2), -- Manufacturer's Suggested Retail Price
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Source/API Identifiers Mapping (Cross-Matching)
-- Links the master canonical product to marketplace-specific identifiers
CREATE TABLE product_cross_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL, -- 'AMAZON', 'EBAY', 'BESTBUY'
    external_id VARCHAR(100) NOT NULL,   -- Amazon ASIN, eBay ItemID, Best Buy SKU
    product_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_platform_external UNIQUE (source_platform, external_id)
);

-- 4. Historical Price Snapshots (Time-Series Table)
-- Where the ETL pipeline ingests price snapshots captured daily via APIs
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

-- 5. Seller Metrics & Offers (Store-level Market Share)
-- Tracks merchant reputation and offer counts per product across platforms
CREATE TABLE seller_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL,
    seller_name VARCHAR(255),
    seller_rating DECIMAL(3, 2),          -- e.g., 4.85 / 5.00
    total_offers_count INT DEFAULT 1,     -- Number of distinct sellers offering the item
    snapshot_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- HIGH-PERFORMANCE INDEXES (Essential for fast Dashboard queries)
-- ============================================================================

-- Accelerates price history lookup by product and date
CREATE INDEX idx_price_snapshots_lookup 
ON price_snapshots(product_id, captured_at DESC);

-- Accelerates price comparison queries grouped by platform
CREATE INDEX idx_price_snapshots_platform 
ON price_snapshots(source_platform, captured_at);

-- Accelerates cross-matching resolution during ETL ingestion
CREATE INDEX idx_cross_mappings_lookup 
ON product_cross_mappings(source_platform, external_id);