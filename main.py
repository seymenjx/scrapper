
import requests
import gc
from db_client import Document
import os

BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

def search_records(year, start_number, end_number, page=1):
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
        print(resp.text)
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
        

    documents = []
    for obj in resp:
        documents.append(
            Document(
                name = f"{obj.get('esasNo')}_{obj.get('kararNo')}",
                doc_id = obj.get('id')
            )
        )
    
    Document.objects.bulk_create(documents)
    del documents
    gc.collect()

#search_records(2009, 1, 99999, 2506)