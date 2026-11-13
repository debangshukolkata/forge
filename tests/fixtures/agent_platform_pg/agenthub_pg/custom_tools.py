"""Custom tools: Python functions an agent can call. Register one in the `tools` table with kind 'custom' and
target 'agenthub_pg.custom_tools:<function>', and give it to an agent in `agent_tools`."""

from __future__ import annotations


def faq() -> str:
    """The answers customers ask for most."""
    return (
        "Password: open Settings, choose Security, press 'Reset password' and follow the link in the e-mail.\n"
        "Invoices: Billing shows every invoice of the last 12 months; each can be downloaded as a PDF.\n"
        "Cancelling: Settings, Plan, 'Cancel plan'. The plan runs until the end of the paid month."
    )
