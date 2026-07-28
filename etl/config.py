import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Carrega as variáveis do arquivo .env localizado na raiz
load_dotenv()

class Config:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgrespassword")
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "market_intelligence")
    
    # URL de conexão do SQLAlchemy
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Cria a engine de conexão do SQLAlchemy
engine = create_engine(Config.DATABASE_URL, echo=False)

# Session Factory para operar transações no banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_connection():
    """
    Testa e retorna uma conexão direta com o PostgreSQL.
    """
    try:
        connection = engine.connect()
        return connection
    except Exception as e:
        print(f" Erro ao conectar ao banco de dados: {e}")
        raise e

if __name__ == "__main__":
    # Teste rápido de conexão
    try:
        conn = get_db_connection()
        print(" Conexão com o PostgreSQL realizada com sucesso!")
        conn.close()
    except Exception:
        print(" Falha na conexão.")