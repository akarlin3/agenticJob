"""Local portfolio text extraction.

The evaluator uploads the portfolio PDF to the Gemini Files API for context
caching, which does NOT yield a local text string. The tailor and coach agents,
however, need the candidate's actual portfolio text inlined into their prompts
so that LIVE-mode resumes / cover letters / interview prep are grounded in the
real person rather than the bundled synthetic persona.

This module extracts the portfolio PDF to plain text once per run, using the
lightweight pure-Python ``pypdf`` dependency (no system libraries required).
"""
import logging

logger = logging.getLogger(__name__)


def extract_portfolio_text(path: str) -> str:
    """Extract plain text from a portfolio PDF at ``path``.

    Returns the concatenated text of every page (stripped). Never raises on a
    malformed / unreadable PDF — instead logs a warning and returns an empty
    string so the caller can fall back gracefully. ``pypdf`` is imported lazily
    so importing this module never hard-fails if the dependency is absent.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(
            "pypdf is not installed; cannot extract portfolio text from %s.", path
        )
        return ""

    try:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as e:  # noqa: BLE001 - extraction must never crash the run
        logger.warning("Failed to extract text from portfolio '%s': %s", path, e)
        return ""

    text = "\n".join(pages).strip()
    if not text:
        logger.warning("Extracted no text from portfolio '%s' (empty or image-only PDF).", path)
    return text
