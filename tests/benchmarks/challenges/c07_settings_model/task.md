Add a `Settings` model in `settings.py` that loads and validates our configuration from a dict: `port` (an integer from 1 to 65535), `debug` (a bool that also accepts the strings "true" and "false"), and `allowed_hosts` (a list of non-empty strings). Bad input must give clear error messages. Use pydantic, it is listed in requirements.txt. Add tests.

You may install packages with `python -m pip install ...` in this project's environment: that is approved.
