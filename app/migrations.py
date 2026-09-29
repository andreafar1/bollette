from sqlalchemy import inspect, text
from .db import engine

BILL_COLUMNS={
 "source_account":"VARCHAR(255)",
 "email_sender":"VARCHAR(500)",
 "email_subject":"VARCHAR(1000)",
 "email_date":"TIMESTAMP",
 "content_hash":"VARCHAR(64)",\n "smart_url":"TEXT"
}
def migrate():
    insp=inspect(engine)
    if "bills" not in insp.get_table_names(): return
    existing={c["name"] for c in insp.get_columns("bills")}
    with engine.begin() as c:
        for name,sqltype in BILL_COLUMNS.items():
            if name not in existing: c.execute(text(f"ALTER TABLE bills ADD COLUMN {name} {sqltype}"))
