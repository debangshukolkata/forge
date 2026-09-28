# Claims API

Flask + flask-smorest service for insurance policies and claims.

## Setup
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt

## Run
    venv\Scripts\flask --app claims_app:create_app run --port 5055

## Test
    venv\Scripts\python -m pytest -q

## Database scripts
Raw SQL scripts live in `sql/`, named `V<nnn>__<description>.sql`, and are run in order.
At startup the app reads database credentials from the `app_config` table (group `database`)
using `BOOTSTRAP_DB_URL`, and exports them as `DB_*` environment variables.
