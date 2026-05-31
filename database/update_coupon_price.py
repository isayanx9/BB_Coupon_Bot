import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:

    try:

        conn.execute(
            text(
                """
                ALTER TABLE coupons
                ADD COLUMN selling_price INTEGER DEFAULT 14
                """
            )
        )

        conn.commit()

        print(
            "✅ selling_price column added"
        )

    except Exception as e:

        print(
            f"⚠️ {e}"
        )