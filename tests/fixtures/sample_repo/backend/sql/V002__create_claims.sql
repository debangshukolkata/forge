-- V002: claims
CREATE TABLE IF NOT EXISTS claims (
    id           BIGSERIAL PRIMARY KEY,
    claim_number VARCHAR(30)    NOT NULL UNIQUE,
    policy_id    BIGINT         NOT NULL REFERENCES policies (id),
    status       VARCHAR(20)    NOT NULL DEFAULT 'submitted',
    category     VARCHAR(30),
    amount       NUMERIC(12, 2) NOT NULL,
    description  TEXT           NOT NULL,
    submitted_at TIMESTAMP      NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_claims_status ON claims (status);

-- Rollback:
-- DROP INDEX IF EXISTS ix_claims_status;
-- DROP TABLE IF EXISTS claims;
