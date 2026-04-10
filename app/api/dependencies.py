from app.core.database import SessionLocal

def get_db():
    db = SessionLocal()    # open session
    try:
        yield db           # give it to the endpoint
    finally:
        db.close()         # always close, even if endpoint crashes

        