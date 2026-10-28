---
id: rcp-django-app
type: recipe
title: A Django app that stays maintainable
summary: "Project layout, settings split by environment, models, views, urls, migrations, N+1 queries and tests with the test client."
moods: [robust, clean]
products: [web app, backend, admin tool]
tags: [django, orm, migrations, settings, select_related, testing]
density: any
dependencies: [django]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: not executed (django is not installed in the build venv); the code follows the documented Django 5 API
---

## A Django app that stays maintainable

Rules:
- One project (`config/`) and small apps (`tickets/`, `accounts/`), each owning its models, views, urls and tests. An app
  that needs three nouns to describe is two apps.
- Split settings: `config/settings/base.py` (shared), `dev.py`, `prod.py`, `test.py`. Secrets, hosts and database URL
  come from environment variables; the code never contains a key. `DEBUG` defaults to off and is turned on only in `dev.py`.
- `prod.py` sets `ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`; run
  `manage.py check --deploy` and fix what it reports.
- Use a custom user model from the first commit (`AUTH_USER_MODEL`); changing it later is painful.
- Put rules in the model or a service function, not in the view; views stay thin (parse, call, render).
- Commit the migration files. Never edit an applied migration; add a new one. Name them (`makemigrations -n add_priority`).
- Every queryset that feeds a template or serializer uses `select_related` (foreign key, one to one) or
  `prefetch_related` (many to many, reverse keys) so the page does a fixed number of queries.
- Add indexes for fields you filter or order by; add `constraints` (unique, check) so the database enforces the rule.

Worked example (a ticket list):

```python
# config/settings/base.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # fails loudly when missing
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

# config/settings/dev.py
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# tickets/models.py
from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    title = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets")
    tags = models.ManyToManyField("Tag", blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        constraints = [models.CheckConstraint(condition=~models.Q(title=""), name="ticket_title_not_empty")]


# tickets/views.py
from django.views.generic import ListView

from .models import Ticket


class TicketList(ListView):
    paginate_by = 25
    template_name = "tickets/list.html"

    def get_queryset(self):
        # one query for tickets+owners, one more for all tags, however many rows
        return (
            Ticket.objects.select_related("owner").prefetch_related("tags").filter(status=Ticket.Status.OPEN)
        )


# tickets/urls.py
from django.urls import path

from .views import TicketList

app_name = "tickets"
urlpatterns = [path("", TicketList.as_view(), name="list")]

# tickets/tests.py
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Ticket


class TicketListTests(TestCase):
    def test_lists_only_open_tickets_in_fixed_query_count(self):
        user = get_user_model().objects.create_user("ana", password="x")  # noqa: S106
        Ticket.objects.create(title="a", owner=user)
        Ticket.objects.create(title="b", owner=user, status=Ticket.Status.DONE)
        with self.assertNumQueries(3):  # count, tickets+owners, tags
            response = self.client.get(reverse("tickets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["object_list"]), 1)
```

The view needs its template, `tickets/templates/tickets/list.html` (a loop over `object_list`), and `Tag` is a model of its own in
`tickets/models.py`. Run with `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test`. Add a login test and a permission test for
every view that is not public (`LoginRequiredMixin`, `UserPassesTestMixin`).

Gotchas:
- `Model.objects.all()` in a template loop, or `ticket.owner.name` inside a loop, is an N+1; `assertNumQueries` catches it.
- `auto_now_add` fields cannot be set in tests or fixtures; use a factory that overrides with `.update()`.
- Data migrations belong in `RunPython` with the historical model (`apps.get_model`), and need a reverse function.
- Adding a non-null column without a default on a big table locks it; add nullable, backfill, then tighten.
- `on_delete=CASCADE` by default silently deletes history; choose PROTECT or SET_NULL on purpose.
- Never serve static or uploaded files with Django in production; use the web server or object storage.
