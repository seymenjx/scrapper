import os
import random
import logging
import asyncio
from dotenv import load_dotenv
import redis
from redis.exceptions import ConnectionError, TimeoutError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from api_scrapper import process_job, get_next_year, get_progress, update_year_status, get_redis_connection
    logger.info("Successfully imported functions")
except ImportError as e:
    logger.error(f"Failed to import functions: {str(e)}")
    raise

async def process_year_async(year):
    logger.info(f"Processing year: {year}")
    progress = get_progress(year)
    if progress:
        try:
            await process_job(year)
            logger.info(f"Completed processing for year {year}")
            update_year_status(year, "completed")
        except Exception as e:
            logger.error(f"Error processing year {year}: {str(e)}")
            update_year_status(year, "pending")  # Reset status to allow retry
    else:
        logger.warning(f"No progress data found for year {year}")
        update_year_status(year, "pending")  # Reset status to allow retry

async def main():
    worker_id = random.randint(1000, 9999)
    logger.info(f"Sub-worker {worker_id} started")
    
    backoff_time = 1
    max_backoff = 60 * 5  # 5 minutes

    while True:
        try:
            year = get_next_year()
            if year is None:
                logger.info(f"Sub-worker {worker_id}: No pending years found. Waiting before next check.")
                await asyncio.sleep(60)  # Wait for 60 seconds before checking again
                continue

            logger.info(f"Sub-worker {worker_id} picked up year: {year}")
            await process_year_async(year)
            backoff_time = 1  # Reset backoff time on successful operation
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis connection error: {str(e)}. Retrying in {backoff_time} seconds.")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, max_backoff)  # Exponential backoff
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}. Retrying in 60 seconds.")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
