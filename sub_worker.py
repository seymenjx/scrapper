import os
import random
import logging
from time import sleep
from dotenv import load_dotenv
import redis
from functions import process_line, get_next_year, get_progress, update_year_status

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pageurl = "https://karararama.yargitay.gov.tr/"

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
    
    while True:
        try:
            year = get_next_year()
            if year is None:
                logger.info(f"Sub-worker {worker_id}: No pending years found. Waiting before next check.")
                sleep(60)  # Wait for 60 seconds before checking again
                continue

            process_year(year)
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis connection error: {str(e)}. Retrying in 30 seconds.")
            sleep(30)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}. Retrying in 60 seconds.")
            sleep(60)

if __name__ == "__main__":
    main()
