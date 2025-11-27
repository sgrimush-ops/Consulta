#!/usr/bin/env python3
import os
import sys
from datetime import date, timedelta
from sqlalchemy import create_engine, text


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        sys.exit(2)

    days = int(os.getenv("CLEANUP_PEDIDOS_DAYS", "7"))
    threshold = date.today() - timedelta(days=days)

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.begin() as conn:
            # Delete approved orders older than threshold
            # Uses data_aprovacao when available
            delete_q = text(
                (
                    "DELETE FROM pedidos_consolidados\n"
                    "WHERE status_aprovacao = 'Aprovado'\n"
                    "  AND COALESCE(CAST(data_aprovacao AS DATE), "
                    "CAST(data_pedido AS DATE)) < :threshold\n"
                    "RETURNING id\n"
                )
            )
            result = conn.execute(delete_q, {"threshold": threshold})
            rows = result.fetchall()
            deleted = len(rows)
        print(
            (
                "Deleted "
                f"{deleted} approved order(s) older than {days} day(s) "
                f"(threshold={threshold})."
            )
        )
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: cleanup pedidos failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
