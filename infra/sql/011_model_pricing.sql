-- Per-model LLM pricing (USD per 1 million tokens).
-- Lets the cost meter price token usage by the model that actually produced
-- it, and lets admins refresh the values from OpenAI's published prices.

CREATE TABLE IF NOT EXISTS model_prices (
    model_name          TEXT PRIMARY KEY,
    input_cost_per_1m   NUMERIC(12, 6) NOT NULL,
    output_cost_per_1m  NUMERIC(12, 6) NOT NULL,
    source              TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dated baseline seed. ON CONFLICT keeps any admin-updated values intact.
-- Source: OpenAI pricing page, captured 2026-05-29.
INSERT INTO model_prices (model_name, input_cost_per_1m, output_cost_per_1m, source)
VALUES
    ('gpt-4o',                 2.50, 10.00, 'seed (OpenAI 2026-05-29)'),
    ('gpt-4o-mini',            0.15,  0.60, 'seed (OpenAI 2026-05-29)'),
    ('text-embedding-3-small', 0.02,  0.00, 'seed (OpenAI 2026-05-29)')
ON CONFLICT (model_name) DO NOTHING;
