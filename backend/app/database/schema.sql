-- SalesCast: single main table. Safe to run repeatedly.
CREATE TABLE IF NOT EXISTS sales (
    id          SERIAL PRIMARY KEY,
    order_id    VARCHAR(30)   NOT NULL UNIQUE,
    order_date  DATE          NOT NULL,
    product     VARCHAR(100)  NOT NULL,
    category    VARCHAR(50)   NOT NULL,
    region      VARCHAR(50)   NOT NULL,
    quantity    INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    discount    NUMERIC(4,2)  NOT NULL CHECK (discount >= 0 AND discount <= 1),
    sales       NUMERIC(12,2) NOT NULL CHECK (sales >= 0),
    profit      NUMERIC(12,2)
);

-- Filters and time-series aggregation hit these columns most.
CREATE INDEX IF NOT EXISTS idx_sales_order_date ON sales (order_date);
CREATE INDEX IF NOT EXISTS idx_sales_category   ON sales (category);
CREATE INDEX IF NOT EXISTS idx_sales_region     ON sales (region);
CREATE INDEX IF NOT EXISTS idx_sales_product    ON sales (product);
