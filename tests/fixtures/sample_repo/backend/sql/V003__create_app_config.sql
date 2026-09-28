-- V003: central configuration, including database credentials read at startup
CREATE TABLE IF NOT EXISTS app_config (
    config_group VARCHAR(50)  NOT NULL,
    config_key   VARCHAR(100) NOT NULL,
    config_value TEXT         NOT NULL,
    PRIMARY KEY (config_group, config_key)
);

-- Rollback:
-- DROP TABLE IF EXISTS app_config;
