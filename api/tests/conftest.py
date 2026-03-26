"""
Conftest: pre-stub app.worker and heavy optional dependencies so that
app.tasks.indexing_tasks can be imported in tests without a broker or
the full Google/OpenAI SDK stack installed.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

from celery import Celery

# Build a real Celery app in eager (synchronous) mode so that @celery_app.task
# decorators register correctly and .apply_async() can be patched normally.
_celery_stub = Celery("test")
_celery_stub.conf.update(task_always_eager=True, task_eager_propagates=True)

_worker_stub = MagicMock()
_worker_stub.celery_app = _celery_stub

# Inject before any test module imports app.worker or app.tasks.indexing_tasks.
sys.modules.setdefault("app.worker", _worker_stub)

# Stub heavy optional dependencies that are not installed in the test venv.
_OPTIONAL_DEPS = [
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.auth.exceptions",
    "google.oauth2",
    "google.oauth2.credentials",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "openai",
    "anthropic",
    "tiktoken",
    "bs4",
    "tidb_vector",
    "tidb_vector.integrations",
    "slack_sdk",
]
for _mod in _OPTIONAL_DEPS:
    sys.modules.setdefault(_mod, MagicMock())
