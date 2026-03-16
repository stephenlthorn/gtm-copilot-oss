#!/usr/bin/env python3
"""Migrate data from PostgreSQL to TiDB Cloud Serverless.

Usage:
    export PG_URL="postgresql://user:pass@localhost:5432/gtm_copilot"
    export TIDB_URL="mysql+pymysql://user:pass@gateway01.us-east-1.prod.aws.tidbcloud.com:4000/gtm_copilot?ssl_ca=/etc/ssl/tidb-ca.pem&ssl_verify_cert=true"
    python scripts/migrate_pg_to_tidb.py
"""
from __future__ import annotations

import json
import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


def main() -> None:
    pg_url = os.environ.get("PG_URL")
    tidb_url = os.environ.get("TIDB_URL")

    if not pg_url or not tidb_url:
        print("Set PG_URL and TIDB_URL environment variables.")
        sys.exit(1)

    pg_engine = create_engine(pg_url)
    tidb_engine = create_engine(tidb_url)

    PGSession = sessionmaker(bind=pg_engine)
    TiDBSession = sessionmaker(bind=tidb_engine)

    inspector = inspect(pg_engine)
    tables = inspector.get_table_names()

    ordered_tables = [
        "kb_config",
        "kb_documents",
        "kb_chunks",
        "chorus_calls",
        "call_artifacts",
        "outbound_messages",
        "audit_logs",
        "google_drive_user_credentials",
        "feishu_user_credentials",
        "user_preferences",
        "ai_feedback",
        "gtm_module_runs",
        "gtm_account_profiles",
        "gtm_risk_signals",
        "gtm_poc_plans",
        "gtm_generated_assets",
        "gtm_trend_insights",
    ]

    migrate_tables = [t for t in ordered_tables if t in tables]

    for table_name in migrate_tables:
        print(f"Migrating {table_name}...")
        with PGSession() as pg_db:
            rows = pg_db.execute(text(f"SELECT * FROM {table_name}")).mappings().all()
            print(f"  Read {len(rows)} rows from PostgreSQL")

        if not rows:
            continue

        with TiDBSession() as tidb_db:
            columns = list(rows[0].keys())
            placeholders = ", ".join(f":{col}" for col in columns)
            col_list = ", ".join(f"`{col}`" for col in columns)
            insert_sql = f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})"

            batch_size = 500
            inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                params = []
                for row in batch:
                    row_dict = dict(row)
                    for col in ("embedding",):
                        if col in row_dict and isinstance(row_dict[col], list):
                            row_dict[col] = json.dumps(row_dict[col])
                    for col in row_dict:
                        val = row_dict[col]
                        if hasattr(val, "hex") and hasattr(val, "int"):
                            row_dict[col] = str(val)
                    params.append(row_dict)

                try:
                    tidb_db.execute(text(insert_sql), params)
                    tidb_db.commit()
                    inserted += len(batch)
                except Exception as e:
                    print(f"  Error inserting batch: {e}")
                    tidb_db.rollback()

            print(f"  Inserted {inserted} rows into TiDB")

    print("\nVerification:")
    for table_name in migrate_tables:
        with PGSession() as pg_db:
            pg_count = pg_db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        with TiDBSession() as tidb_db:
            tidb_count = tidb_db.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar()
        status = "OK" if pg_count == tidb_count else "MISMATCH"
        print(f"  {table_name}: PG={pg_count} TiDB={tidb_count} [{status}]")


if __name__ == "__main__":
    main()
