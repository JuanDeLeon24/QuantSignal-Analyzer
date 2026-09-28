from journal.repository import TradeJournal
from reports.html_report import generate_html_report


def create_history_dashboard(journal=None):
    """Genera el reporte HTML de la bitacora (reemplaza el PNG anterior)."""
    own = journal is None
    journal = journal or TradeJournal()
    try:
        path = generate_html_report(journal)
        print("\n✅ Reporte de bitacora generado")
        print("  ", path)
        return path
    finally:
        if own:
            journal.close()
