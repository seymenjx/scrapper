
import requests
import gc
from db_client import Document
import os
import time

BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

def search_records(year, start_number, end_number, file, page=1):
    print(f'searching records for {year} for {page} page')
    payload = {
        "data": {
            "esasYil": str(year),
            "esasIlkSiraNo": str(start_number),
            "esasSonSiraNo": str(end_number),
            "pageSize": 100,
            "pageNumber": page,
        }
    }
    try:
        resp = requests.post(
        url=SEARCH_URL,
        json=payload
        )
        resp = resp.json().get("data").get("data")
        if not resp:
            print('fucked')
            return

    except Exception as e:
        print(f'request exception {e}')

        # Check if a progress file exists to resume work
        if os.path.exists("progress_file.txt"):
            with open("progress_file.txt", 'a') as f:
                f.write(f"{year}-{page} \n")
        
        time.sleep(10)
        
        return

    documents = ''
    for obj in resp:
        documents += f"{obj.get('esasNo')}_{obj.get('kararNo')}-{obj.get('id')}\n"
    
    with open(file, 'a') as f:
        f.write(documents)

    del documents
    gc.collect()

for i in range(1, 439+1):
    search_records(2024, 1, 99999, "complete_2024.txt", i)