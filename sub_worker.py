import os
import random
import logging
from time import sleep
from dotenv import load_dotenv
import redis
from redis.exceptions import ConnectionError, TimeoutError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from functions import process_line, get_next_year, get_progress, update_year_status, get_redis_connection
    logger.info("Successfully imported functions")
except ImportError as e:
    logger.error(f"Failed to import functions: {str(e)}")
    raise

pageurl = "https://karararama.yargitay.gov.tr/"

def process_year(year):
    logger.info(f"Processing year: {year}")
    progress = get_progress(year)
    if progress:
        try:
            process_line(year, pageurl, progress['end'], progress['where_it_left_off'])
            logger.info(f"Completed processing for year {year}")
            update_year_status(year, "completed")
        except Exception as e:
            logger.error(f"Error processing year {year}: {str(e)}")
            update_year_status(year, "pending")  # Reset status to allow retry
    else:
        logger.warning(f"No progress data found for year {year}")
        update_year_status(year, "pending")  # Reset status to allow retry

def main():
    worker_id = random.randint(1000, 9999)
    logger.info(f"Sub-worker {worker_id} started")
    
    backoff_time = 1
    max_backoff = 60 * 5  # 5 minutes

    while True:
        try:
            year = get_next_year()
            if year is None:
                logger.info(f"Sub-worker {worker_id}: No pending years found. Waiting before next check.")
                sleep(60)  # Wait for 60 seconds before checking again
                continue

            logger.info(f"Sub-worker {worker_id} picked up year: {year}")
            process_year(year)
            backoff_time = 1  # Reset backoff time on successful operation
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis connection error: {str(e)}. Retrying in {backoff_time} seconds.")
            sleep(backoff_time)
            backoff_time = min(backoff_time * 2, max_backoff)  # Exponential backoff
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}. Retrying in 60 seconds.")
            sleep(60)

if __name__ == "__main__":
    main()
