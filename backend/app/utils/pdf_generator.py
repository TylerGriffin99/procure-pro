"""Generate payment recommendation PDF using WeasyPrint."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def generate_payment_recommendation_pdf(data: dict) -> bytes:
    """Generate a payment recommendation PDF from assessment data.

    Args:
        data: Dict containing all PR fields (see template for expected keys)

    Returns:
        PDF file contents as bytes
    """
    # Lazy on purpose: weasyprint pulls in cairo/pango natively and is only needed for PDF export.
    from weasyprint import HTML

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("payment_recommendation.html")
    html_content = template.render(**data)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
