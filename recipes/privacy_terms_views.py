from django.http import HttpResponse
from django.views.decorators.http import require_GET
import pathlib

@require_GET
def privacy_policy(request):
    md_path = pathlib.Path(__file__).parent.parent / "docs" / "PRIVACY_TERMS_TEMPLATE.md"
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    # Simple markdown to HTML (for production, use markdown2 or similar)
    html = f"<html><body><pre>{content}</pre></body></html>"
    return HttpResponse(html)

@require_GET
def terms(request):
    md_path = pathlib.Path(__file__).parent.parent / "docs" / "PRIVACY_TERMS_TEMPLATE.md"
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    # Extract only terms section
    terms_start = content.find("# Användarvillkor")
    html = f"<html><body><pre>{content[terms_start:]}</pre></body></html>"
    return HttpResponse(html)
