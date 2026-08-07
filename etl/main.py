import os
import logging
from dotenv import load_dotenv

# Importa as etapas do pipeline
from etl.extract import run_extraction
from etl.transform import run_pipeline
from etl.load import run_loader
from etl.config import test_db_connection

# Configuração Centralizada de Logs
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
logger = logging.getLogger("ETL_Orchestrator")

load_dotenv()

def main():
    logger.info("==================================================")
    logger.info("Starting ETL Pipeline ")
    logger.info("==================================================")

    # Passo 1: Verificar conectividade com o banco de dados antes de gastar recursos
    logger.info("Step 1/4: Checking database connection...")
    if not test_db_connection():
        logger.error(" Pipeline aborted: Failed to connect to PostgreSQL.")
        return

    try:
        # Passo 2: Extração dos dados brutos das fontes/APIs
        logger.info("Step 2/4: Running Extraction...")
        raw_data = run_extraction()
        logger.info("Extraction completed successfully.")

        # Passo 3: Transformação e limpeza dos dados
        logger.info("Step 3/4: Running Transformation...")
        processed_data_path = run_pipeline()
        logger.info(f"Transformation completed. Processed file: {processed_data_path}")

        # Passo 4: Carga relacional no PostgreSQL
        logger.info("Step 4/4: Running Relational Database Load...")
        run_loader()
        
        logger.info("==================================================")
        logger.info("ETL Pipeline completed ")
        logger.info("==================================================")

    except Exception as e:
        logger.error(f"❌ Critical error during ETL execution: {e}")
        raise e

if __name__ == "__main__":
    main()