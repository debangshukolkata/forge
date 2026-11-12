"""Custom tools: Python functions an agent can call. Register one in the `tools` table with kind 'custom' and
target 'agenthub.custom_tools:<function>', and give it to an agent in `agent_tools`."""

from __future__ import annotations

import json

from agenthub import deployment_api


def invoice_total() -> str:
    """The sum of this month's invoices."""
    invoices = json.loads(deployment_api.call("/api/v1/invoices"))["items"]
    return json.dumps({"total": sum(invoice["amount"] for invoice in invoices)})
