import requests
import gc
from bs4 import BeautifulSoup
import os
import time

BASE_URL = "https://karararama.yargitay.gov.tr"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def download_file(name, doc_id):
    try:
        resp = requests.get(DOCUMENT_URL, params={"id": doc_id})
        resp = resp.json().get("data")

        if not resp:
            print('fucked')
            return False
        
        name = name.replace('/', '-')
        
        with open(f"out/{name.split('-')[0]}/{name}.txt", 'w') as f:
            f.write(extract_text_from_html(resp))
            print(f'downloaded {name}-{doc_id}')
        return True
    except Exception as e:
        print(f'request exception {e}')
        return False


if __name__ == '__main__':
    with open('pick.txt', 'r') as f:
        for line in f:
            name, id = line.strip().split('-')
            name = name.strip()
            id = int(id)
            print(f'downloading {name} for {id}')
            download_file(name, id)
            gc.collect()