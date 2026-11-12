CREATE TABLE agents (
    name TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    max_context_chars INTEGER NOT NULL
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

INSERT INTO agents VALUES ('ops', 'Answers questions about what is deployed', 20000);
INSERT INTO agents VALUES ('billing', 'Answers questions about invoices', 20000);

INSERT INTO tools VALUES ('list_deployments', 'native', 'List the deployments that exist, with all their details', '/api/v1/applications');
INSERT INTO tools VALUES ('get_cluster_version', 'native', 'Show the version of the cluster', '/api/v1/version');
INSERT INTO tools VALUES ('list_invoices', 'native', 'List the invoices of this month', '/api/v1/invoices');

INSERT INTO agent_tools VALUES ('ops', 'list_deployments');
INSERT INTO agent_tools VALUES ('ops', 'get_cluster_version');
INSERT INTO agent_tools VALUES ('billing', 'list_invoices');
