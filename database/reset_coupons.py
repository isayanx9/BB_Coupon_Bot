import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from sqlalchemy import text
from database.db import engine

with engine.connect() as conn:
    conn.execute(
        text("DROP TABLE IF EXISTS coupons")
    )
    conn.commit()

print("✅ Coupons Table Deleted")