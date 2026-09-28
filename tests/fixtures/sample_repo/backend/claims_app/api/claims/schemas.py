from __future__ import annotations

from marshmallow import Schema, fields, validate

CLAIM_STATUSES = ["submitted", "triaged", "approved", "rejected"]


class ClaimSchema(Schema):
    id = fields.Integer(dump_only=True)
    claim_number = fields.String(dump_only=True)
    policy_id = fields.Integer()
    status = fields.String(dump_only=True)
    category = fields.String(dump_only=True, allow_none=True)
    amount = fields.Float()
    description = fields.String()
    submitted_at = fields.DateTime(dump_only=True)


class ClaimCreateSchema(Schema):
    policy_id = fields.Integer(required=True)
    amount = fields.Float(required=True)
    description = fields.String(required=True, validate=validate.Length(min=10, max=2000))


class ClaimQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    status = fields.String(load_default=None, validate=validate.OneOf(CLAIM_STATUSES))


class ClaimPageSchema(Schema):
    items = fields.List(fields.Nested(ClaimSchema))
    total = fields.Integer()
    page = fields.Integer()
    page_size = fields.Integer()


class ClaimTriageSchema(Schema):
    claim_id = fields.Integer()
    category = fields.String()
    priority = fields.String()
    summary = fields.String()
