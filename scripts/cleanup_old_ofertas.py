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

    older_than_days = int(os.getenv("CLEANUP_OLDER_THAN_DAYS", "1"))
    threshold = date.today() - timedelta(days=older_than_days)

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.begin() as conn:
            # PostgreSQL supports DELETE ... RETURNING
            delete_q = text(
                "DELETE FROM ofertas WHERE data_final < :threshold "
                "RETURNING id"
            )
            result = conn.execute(delete_q, {"threshold": threshold})
            rows = result.fetchall()
            deleted = len(rows)
        print(
            (
                "Deleted "
                f"{deleted} old offer(s) older than {older_than_days} day(s) "
                f"(threshold={threshold})."
            )
        )
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: cleanup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
