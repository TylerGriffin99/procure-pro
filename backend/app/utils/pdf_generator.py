"""Generate payment recommendation PDF using WeasyPrint."""
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# WeasyPrint needs pango/cairo libs from Homebrew. On macOS with Anaconda Python,
# the dynamic linker doesn't search /opt/homebrew/lib by default.
if "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ:
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = "/opt/homebrew/lib"

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def generate_payment_recommendation_pdf(data: dict) -> bytes:
    """Generate a payment recommendation PDF from assessment data.

    Args:
        data: Dict containing all PR fields (see template for expected keys)

    Returns:
        PDF file contents as bytes
    """
    from weasyprint import HTML

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("payment_recommendation.html")
    html_content = template.render(**data)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
