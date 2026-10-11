from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.schemas.payment_recommendation import PaymentRecommendation

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def generate_payment_recommendation_pdf(rec: PaymentRecommendation) -> bytes:
    # Lazy on purpose: weasyprint pulls in cairo/pango natively and is only needed for PDF export.
    from weasyprint import HTML

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("payment_recommendation.html")
    html_content = template.render(**rec.model_dump())
    pdf_bytes = HTML(string=html_content).write_pdf()
    if pdf_bytes is None:
        raise RuntimeError("weasyprint returned no PDF bytes for payment recommendation")
    return pdf_bytes
