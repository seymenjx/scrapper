from multiprocessing import Process
from main import search_records
import os

# Year and their corresponding maximum pages
year_max_page = [
    (2007, 1835),
    (2008, 2234),
    (2009, 3302),
    (2010, 4625),
    (2011, 6811),
    (2012, 7533),
    (2013, 8549),
    (2014, 9439),
    (2015, 10044),
    (2016, 8077),
    (2017, 4878),
    (2018, 3533),
    (2019, 4076),
    (2020, 4128),
    (2021, 4550),
    (2022, 2515),
    (2023, 1753),
    (2024, 439),
]

def search_records(year, start_number, end_number, page=1):
    # Your actual implementation goes here
    print(f"Processing Year: {year}, Page: {page}")

def worker(year, start_page, end_page):
    progress_file = f"progress_{year}_{start_page}_{end_page}.txt"

    # Check if a progress file exists to resume work
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            last_page_processed = int(f.read())
            current_page = last_page_processed + 1
    else:
        current_page = start_page

    for page in range(current_page, end_page + 1):
        try:
            search_records(year, 1, 999999, page=page)
            # Save progress after each page is processed
            with open(progress_file, 'w') as f:
                f.write(str(page))
        except Exception as e:
            print(f"Error processing Year: {year}, Page: {page}. Error: {e}")
            # Optionally, you can decide whether to continue or break
            break

    # Remove the progress file if all pages have been processed
    if os.path.exists(progress_file):
        os.remove(progress_file)

def main():
    processes = []

    for year, max_page in year_max_page:
        # Calculate the number of pages per worker
        pages_per_worker = max_page // 4
        remainder = max_page % 4
        page_ranges = []
        start_page = 1

        # Divide pages into four ranges
        for i in range(4):
            end_page = start_page + pages_per_worker - 1
            if remainder > 0:
                end_page += 1
                remainder -= 1
            page_ranges.append((start_page, end_page))
            start_page = end_page + 1

        # Spawn a worker for each page range
        for start, end in page_ranges:
            p = Process(target=worker, args=(year, start, end))
            processes.append(p)
            p.start()

    # Wait for all processes to complete
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
