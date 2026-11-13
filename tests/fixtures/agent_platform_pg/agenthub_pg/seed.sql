CREATE TABLE agents (
    name TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    max_context_chars INTEGER NOT NULL,
    system_prompt TEXT NOT NULL
);

-- kind 'native': the tool is a call to the deployment API; `target` is the API path.
-- kind 'custom': the tool is a Python function; `target` is "module:function".
CREATE TABLE tools (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('native', 'custom')),
    description TEXT NOT NULL,
    target TEXT NOT NULL
);

CREATE TABLE agent_tools (
    agent TEXT NOT NULL REFERENCES agents(name),
    tool TEXT NOT NULL REFERENCES tools(name),
    PRIMARY KEY (agent, tool)
);

INSERT INTO agents VALUES ('ops', 'Answers questions about what is deployed', 20000,
    'You answer questions about what is deployed. Use your tools and answer only from what they return.');
INSERT INTO agents VALUES ('billing', 'Answers questions about invoices', 20000,
    'You answer questions about invoices. Use your tools and answer only from what they return.');
INSERT INTO agents VALUES ('support', 'Answers customers'' questions', 20000,
    'You are the customer support agent. Use your tool to look up the answer. Always answer in English.');

INSERT INTO tools VALUES ('list_deployments', 'native', 'List the deployments that exist, with all their details', '/api/v1/applications');
INSERT INTO tools VALUES ('get_cluster_version', 'native', 'Show the version of the cluster', '/api/v1/version');
INSERT INTO tools VALUES ('list_invoices', 'native', 'List the invoices of this month', '/api/v1/invoices');
INSERT INTO tools VALUES ('faq_lookup', 'custom', 'Look up the answers customers ask for most: password, invoices, cancelling', 'agenthub_pg.custom_tools:faq');

INSERT INTO agent_tools VALUES ('ops', 'list_deployments');
INSERT INTO agent_tools VALUES ('ops', 'get_cluster_version');
INSERT INTO agent_tools VALUES ('billing', 'list_invoices');
INSERT INTO agent_tools VALUES ('support', 'faq_lookup');
