from functions import redis_client, save_progress, get_next_year, get_progress
import json
import os
from dotenv import load_dotenv
import logging


load_dotenv()

# TODO: add all years
all_years = [
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
    print("Starting Redis initialization...")
    if not redis_client.exists('scraping_progress'):
        for year_data in all_years:  # Ensure all_years is defined and contains the years you want to process
            year, start, end, start_number = year_data
            progress = json.dumps({
                'page': 1,
                'begin': start_number,
                'start': start,
                'end': end,
                'start_number': start_number,
                'status': 'pending'
            })
            redis_client.hset('scraping_progress', str(year), progress)
            print(f"Added year {year} to Redis")
        print("Redis initialization complete")
    else:
        print("Redis already initialized, skipping initialization")
    
    # Print the contents of scraping_progress after initialization
    all_years = redis_client.hgetall('scraping_progress')
    print("Current contents of scraping_progress:", all_years)

def main():
    try:
        initialize_redis()  # Ensure Redis is initialized
        while True:
            year = get_next_year()
            if year is None:
                print("All years processed")
                break

            print(f"Processing year: {year}")
            progress = get_progress(year)
            if progress:
                try:
                    # Here you would call the sub-worker processing function
                    # For example: process_line(year, pageurl, progress['start'], progress['end'], progress['start_number'])
                    print(f"Completed processing for year {year}")
                except Exception as e:
                    logging.error(f"Error processing year {year}: {str(e)}")
                    print(f"Error processing year {year}: {str(e)}")
            else:
                print(f"No progress data found for year {year}")
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}")
        print(f"Fatal error in main: {str(e)}")

if __name__ == "__main__":
    main()
