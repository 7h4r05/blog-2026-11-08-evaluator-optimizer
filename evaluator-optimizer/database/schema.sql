-- country_code: ISO 3166-1 alpha-2, for example 'PL' or 'DE'
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL
);

-- status: 'new', 'paid' or 'cancelled'
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    ordered_at TEXT NOT NULL,  -- ISO date, YYYY-MM-DD
    status TEXT NOT NULL,
    total REAL NOT NULL
);

CREATE INDEX idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_total ON orders(total);
