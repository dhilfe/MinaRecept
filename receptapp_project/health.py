from __future__ import annotations

import os

from django.http import JsonResponse
from django.http import HttpRequest


def health(request: HttpRequest):
    return JsonResponse(
        {
            "status": "ok",
            "git_sha": os.environ.get("GIT_SHA", "unknown"),
        }
    )
