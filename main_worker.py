from functions import get_redis_connection, get_next_year, get_progress, check_redis_connection, update_year_status
import json
import os
from dotenv import load_dotenv
import logging
import time


load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TODO: add all years
ALL_YEARS = [
    [2015, 1, 5044, 999999],
    [2015, 1, 5000, 11215],
    [2014, 1, 4439, 999999],
    [2014, 1, 5000, 13795],
    [2013, 1, 3476, 999999],
    [2013, 1, 5000, 14844],
    [2016, 1, 3077, 999999],
    [2016, 1, 5000, 12092],
    [2011, 1, 1542, 999999],
    [2023, 1, 1611, 999999],
    [2024, 1, 273, 999999],
    [2012, 1, 2246, 999999],
    [2012, 1, 5000, 17086],
    [2021, 1, 4468, 999999],
    [2010, 1, 4414, 999999],
    [2020, 1, 4126, 999999],
    [2019, 1, 4076, 999999],
    [2018, 1, 3533, 999999],
    [2009, 1, 3167, 999999],
    [2022, 1, 2454, 999999],
    [2008, 1, 2186, 999999],
    [2007, 1, 1813, 999999],
    [2011, 1, 5000, 20645]
]

def initialize_redis():
    logger.info("Starting Redis initialization...")
    redis_client = get_redis_connection()
    if not redis_client.exists('scraping_progress'):
        for year_data in ALL_YEARS:
            year, start, end, start_number = year_data
            progress = json.dumps({
                'page': 1,
                'where_it_left_off': start_number,
                'start': start,
                'end': end,
                'status': 'pending'
            })
            redis_client.hset('scraping_progress', str(year), progress)
            logger.info(f"Added year {year} to Redis")
        logger.info("Redis initialization complete")
    else:
        logger.info("Redis already initialized, skipping initialization")
    
    all_years = redis_client.hgetall('scraping_progress')
    logger.info(f"Current contents of scraping_progress: {all_years}")

def reset_progress():
    redis_client = get_redis_connection()
    all_years = redis_client.hgetall('scraping_progress')
    for year, data_str in all_years.items():
        data = json.loads(data_str)
        data['status'] = 'pending'
        redis_client.hset('scraping_progress', year, json.dumps(data))
    logger.info("All years reset to pending status")

def main():
    try:
        initialize_redis()
        reset_progress()
        logger.info("Redis initialized and progress reset")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")

if __name__ == "__main__":
    if check_redis_connection():
        main()
    else:
        logger.error("Exiting due to Redis connection failure")
