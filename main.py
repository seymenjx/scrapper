
import requests
import gc
from db_client import Document

BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

def search_records(year, start_number, end_number, page=1):
    payload = {
        "data": {
            "esasYil": str(year),
            "esasIlkSiraNo": str(start_number),
            "esasSonSiraNo": str(end_number),
            "pageSize": 100,
            "pageNumber": page,
        }
    }


    resp = requests.post(
        url=SEARCH_URL,
        json=payload
    )
    try:
        resp = resp.json().get("data").get("data")
        if not resp:
            return

    except Exception as e:
        return

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
