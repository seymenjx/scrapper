from functions import process_line, get_next_year, get_progress
import os
from dotenv import load_dotenv
from time import sleep

# Load environment variables
load_dotenv()

pageurl = "https://karararama.yargitay.gov.tr/"

def main():
    sleep(10)
    while True:
        year = get_next_year()
        if year is None:
            print("All years processed")
            break

        print(f"Processing year: {year}")
        progress = get_progress(year)
        if progress:
            try:
                process_line(year, pageurl, progress['start'], progress['end'], progress['start_number'])
                print(f"Completed processing for year {year}")
            except Exception as e:
                print(f"Error processing year {year}: {str(e)}")
        else:
            print(f"No progress data found for year {year}")

if __name__ == "__main__":
    main()