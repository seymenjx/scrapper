import os
import random
import logging
from time import sleep
from dotenv import load_dotenv
import redis
from redis.exceptions import ConnectionError, TimeoutError
from functions import process_line, get_next_year, get_progress, update_year_status

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pageurl = "https://karararama.yargitay.gov.tr/"

# Create a Redis connection pool
redis_pool = redis.ConnectionPool.from_url(os.getenv('REDIS_URL'), max_connections=10)

def get_redis_connection():
    return redis.Redis(connection_pool=redis_pool)

def process_year(year):
    logger.info(f"Processing year: {year}")
    progress = get_progress(year)
    if progress:
        try:
            process_line(year, pageurl, progress['start'], progress['end'], progress['start_number'])
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
            redis_client = get_redis_connection()
            year = get_next_year(redis_client)
            if year is None:
                logger.info(f"Sub-worker {worker_id}: No pending years found. Waiting before next check.")
                sleep(60)  # Wait for 60 seconds before checking again
                continue

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
