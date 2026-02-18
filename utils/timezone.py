from datetime import date, datetime
from zoneinfo import ZoneInfo

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def now_brazil() -> datetime:
    """Retorna datetime atual de Brasília sem tzinfo (compatível com TIMESTAMP)."""
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)


def today_brazil() -> date:
    """Retorna a data atual no fuso de Brasília."""
    return datetime.now(BRAZIL_TZ).date()
