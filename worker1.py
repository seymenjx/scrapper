from functions import process_line, redis_client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

pageurl = "https://karararama.yargitay.gov.tr/"
year_data = [2015, 1, 5044, 999999]

def main():
    year = year_data[0]
    
    try:
        process_line(year, pageurl, year_data[1], year_data[2], year_data[3])
    except Exception as e:
        print(f"Error processing year {year}: {str(e)}")
    finally:
        # Clear progress after successfully processing the year
        redis_client.delete(f'progress:{year}')

if __name__ == "__main__":
    main()
