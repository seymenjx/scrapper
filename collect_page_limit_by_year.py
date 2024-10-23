
import requests
import gc
from db_client import Document

BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

def collect_max_page(year, start_number, end_number, page=1):
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
        resp = resp.json().get("data").get("draw")
        if not resp:
            return

    except Exception as e:
        return

    return (year, resp+1)


if __name__ == '__main__':
    years = range(2007, 2025)
    res = []
    for year in years:
        res.append(collect_max_page(year, 1, 999999))
    
    print(res)
