import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuração do Logger unificado
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ETL_Config")

load_dotenv()

class Config:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgrespassword")
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "market_intelligence")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

engine = create_engine(Config.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Gerenciador de contexto de sessão ORM.
    Garante abertura e fechamento seguro de conexões.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_db_connection():
    """Testa a conectividade com o PostgreSQL."""
    try:
        with engine.connect() as conn:
            logger.info("Conexão com o PostgreSQL realizada com sucesso!")
            return True
    except Exception as e:
        logger.error(f"Falha na conexão com o banco de dados: {e}")
        return False

if __name__ == "__main__":
    test_db_connection()