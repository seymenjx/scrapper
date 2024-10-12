from functions import redis_client, save_progress, get_next_year, get_progress
import json
import os
from dotenv import load_dotenv


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
    # Initialize Redis with all years if not already set
    if not redis_client.exists('scraping_progress'):
        for year_data in all_years:
            year, start, end, start_number = year_data
            save_progress(year, 1, start_number, start, end, start_number, status='pending')

def main():
    initialize_redis()  # Initialize Redis at the start
    print("Main worker initialized. Sub-workers can now start processing.")
    
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
                print(f"Error processing year {year}: {str(e)}")
        else:
            print(f"No progress data found for year {year}")

if __name__ == "__main__":
    main()
