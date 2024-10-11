from functions import redis_client, save_progress
import json
import os
from dotenv import load_dotenv


load_dotenv()

#TODO add all years
all_years = [
    [2015, 1, 5044, 999999],
    [2023, 1, 1611, 999999],
    [2022, 1, 2454, 999999],
    # ... add all other years here
    [2007, 1, 1813, 999999]
]

def initialize_redis():
    # Initialize Redis with all years if not already set
    if not redis_client.exists('scraping_progress'):
        for year_data in all_years:
            year, start, end, start_number = year_data
            save_progress(year, 1, start_number, start, end, start_number, status='pending')

def main():
    initialize_redis()
    print("Main worker initialized. Sub-workers can now start processing.")

if __name__ == "__main__":
    main()