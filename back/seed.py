from app.database import SessionLocal, create_schema
from app.seed import seed_database


if __name__ == "__main__":
    create_schema()
    with SessionLocal() as session:
        inserted = seed_database(session)
    print("Seed demo berhasil dibuat." if inserted else "Database sudah berisi data; seed dilewati.")

