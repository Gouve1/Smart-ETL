import os
import glob
import logging
from dotenv import load_dotenv

from etl.load import run_loader, test_db_connection

# Centralized Log Configuration
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

def get_latest_processed_file(processed_dir="data/processed"):
    """Scans the processed directory and returns the path of the most recent JSON file."""
    if not os.path.exists(processed_dir):
        logger.warning(f"Directory {processed_dir} not found.")
        return None
    
    json_files = glob.glob(os.path.join(processed_dir, "processed_products_*.json"))
    if not json_files:
        return None
    
    # Returns the file based on the most recent modification time
    latest_file = max(json_files, key=os.path.getmtime)
    return latest_file

def main():
    logger.info("==================================================")
    logger.info("Starting ETL Pipeline Orchestration")
    logger.info("==================================================")

    # Step 1: Check PostgreSQL connectivity
    logger.info("Step 1/3: Checking database connection...")
    if not test_db_connection():
        logger.error("Pipeline aborted: Failed to connect to PostgreSQL.")
        return

    # Step 2: Locate transformed data
    logger.info("Step 2/3: Searching for the latest processed data...")
    target_file = get_latest_processed_file()
    
    if not target_file:
        logger.error("Pipeline aborted: No processed JSON file found.")
        return
    
    logger.info(f"Target file selected: {target_file}")

    # Step 3: Execute relational database load
    logger.info("Step 3/3: Executing relational database load...")
    try:
        run_loader()
        logger.info("==================================================")
        logger.info("ETL Pipeline completed with ABSOLUTE SUCCESS!")
        logger.info("==================================================")
    except Exception as e:
        logger.error(f"Critical error during ETL execution: {e}")
        raise e

if __name__ == "__main__":
    main()