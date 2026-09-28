-- V001: policies
CREATE TABLE IF NOT EXISTS policies (
    id            BIGSERIAL PRIMARY KEY,
    policy_number VARCHAR(30)  NOT NULL UNIQUE,
    holder_name   VARCHAR(120) NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'active',
    start_date    DATE         NOT NULL,
    end_date      DATE         NOT NULL
);

-- Rollback:
-- DROP TABLE IF EXISTS policies;
