import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from config import DATABASE_URL
from database.models import Base

engine = create_engine(DATABASE_URL)

Base.metadata.create_all(engine)

print("✅ Tables Created Successfully!")