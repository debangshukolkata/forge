---
name: flask-smorest-endpoint
description: Add a REST endpoint to a Flask + flask-smorest app (blueprint, marshmallow schemas, service, repository, tests, OpenAPI check).
---
# Adding a flask-smorest endpoint

1. Find the closest existing endpoint of the same kind (list / detail / create) and mirror it exactly:
   blueprint module layout, route style (function routes vs MethodView), decorators order, error handling.
2. Schemas (marshmallow): request schema for `@blp.arguments(Schema, location="json"|"query")`, response
   schema for `@blp.response(status, Schema)`. Pagination: reuse the app's existing pagination pattern
   (`@blp.paginate()` or explicit page/page_size query args) — don't invent a new one.
3. Keep business logic in the service layer; the route only parses, calls the service, returns.
4. Data access in the repository layer, using the app's existing style (raw SQL via `session.execute(text(...))`
   with bound parameters, or the ORM). Never build SQL with string formatting.
5. Errors: raise the app's own exception types (e.g. `NotFoundError`) so its error handlers produce the
   standard JSON body and status code.
6. Auth: reuse the existing decorator (e.g. `@jwt_required`) in the same position as other routes.
7. Register the blueprint where the app registers the others (e.g. `register_blueprints(api)`).
8. Tests with the app's fixtures (`client`, auth headers, seeded data): happy path, not found, validation
   error, auth required. Then `openapi_check` with `expect_paths` to confirm the route and schemas appear.
