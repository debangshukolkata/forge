from __future__ import annotations

from marshmallow import Schema, fields


class PolicySchema(Schema):
    id = fields.Integer()
    policy_number = fields.String()
    holder_name = fields.String()
    status = fields.String()
    start_date = fields.Date()
    end_date = fields.Date()
