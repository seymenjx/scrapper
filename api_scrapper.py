import asyncio
import aiohttp
import json
import os
import logging
import time
import random
from bs4 import BeautifulSoup
import aioboto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import redis
from urllib.parse import urlparse
import ssl

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

REDIS_URL = os.getenv('REDIS_URL')

if not REDIS_URL:
    logger.error("REDIS_URL environment variable is not set")
    raise ValueError("REDIS_URL environment variable is not set")

# Parse the Redis URL
parsed_url = urlparse(REDIS_URL)

if parsed_url.scheme not in ("redis", "rediss"):
    logger.error(f"Invalid REDIS_URL scheme: {parsed_url.scheme}. Expected 'redis' or 'rediss'.")
    raise ValueError(f"Invalid REDIS_URL scheme: {parsed_url.scheme}. Expected 'redis' or 'rediss'.")

# Determine if SSL should be used
use_ssl = parsed_url.scheme == "rediss"

# Create a Redis connection pool
try:
    connection_kwargs = {
        'max_connections': 20,
    }
    
    if use_ssl:
        connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
    
    redis_pool = redis.ConnectionPool.from_url(REDIS_URL, **connection_kwargs)
    logger.info("Redis connection pool created successfully")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Failed to create Redis connection pool: {str(e)}")
    raise

def get_redis_connection():
    try:
        return redis.Redis(connection_pool=redis_pool)
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Failed to get Redis connection: {str(e)}")
        raise

def get_progress(year):
    redis_client = get_redis_connection()
    progress = redis_client.hget('scraping_progress', str(year))
    if progress:
        return json.loads(progress)
    return None

def save_progress(year, page, end, left_off, status='in_progress'):
    progress = json.dumps({
        'year': year,
        'page': page,
        'end': end,
        'where_it_left_off': left_off,
        'status': status
    })
    redis_client = get_redis_connection()
    redis_client.hset('scraping_progress', str(year), progress)

def check_redis_connection():
    try:
        redis_client = get_redis_connection()
        redis_client.ping()
        print("Successfully connected to Redis")
        return True
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        return False

def update_year_status(year, status):
    try:
        redis_client = get_redis_connection()
        current_data = redis_client.hget("scraping_progress", str(year))
        if current_data:
            data = json.loads(current_data)
            data['status'] = status
            redis_client.hset("scraping_progress", str(year), json.dumps(data))
            logger.info(f"Updated status for year {year} to {status}")
        else:
            logger.warning(f"No data found for year {year} when updating status")
    except Exception as e:
        logger.error(f"Error updating year status: {str(e)}")


def get_next_year():
    redis_client = get_redis_connection()
    logger.info("Attempting to get next year from Redis")
    try:
        while True:
            all_years = redis_client.hgetall('scraping_progress')
            logger.info(f"Retrieved {len(all_years)} years from Redis")
            
            for year, data_str in all_years.items():
                data = json.loads(data_str)
                if data['status'] == 'pending':
                    year_int = int(year.decode('utf-8'))
                    
                    # Try to atomically update the status to 'in_progress'
                    pipeline = redis_client.pipeline()
                    pipeline.hget('scraping_progress', year)
                    pipeline.hset('scraping_progress', year, json.dumps({**data, 'status': 'in_progress'}))
                    result = pipeline.execute()
                    
                    # Check if the update was successful (i.e., the data hasn't changed)
                    if result[0].decode('utf-8') == data_str.decode('utf-8'):
                        logger.info(f"Successfully claimed year: {year_int}")
                        return year_int
                    else:
                        logger.info(f"Year {year_int} was already claimed, trying next")
            
            # If we've checked all years and found none, wait a bit before trying again
            logger.info("No pending years found, waiting before retry")
            time.sleep(5)
        
    except Exception as e:
        logger.error(f"Error in get_next_year: {str(e)}")
        return None


async def search_records(session, year, start_number, end_number, page=1):
    payload = {
        "data": {
            "arananKelime": "",
            "esasYil": str(year),
            "esasIlkSiraNo": str(start_number),
            "esasSonSiraNo": str(end_number),
            "kararYil": "",
            "kararIlkSiraNo": "",
            "kararSonSiraNo": "",
            "baslangicTarihi": "",
            "bitisTarihi": "",
            "siralama": "1",
            "siralamaDirection": "desc",
            "birimYrgKurulDaire": "",
            "birimYrgHukukDaire": "",
            "birimYrgCezaDaire": "",
            "pageSize": 100,
            "pageNumber": page
        }
    }
    
    async with session.post(SEARCH_URL, json=payload) as response:
        response.raise_for_status()
        return await response.json()

async def get_document(session, doc_id):
    params = {"id": doc_id}
    async with session.get(DOCUMENT_URL, params=params) as response:
        response.raise_for_status()
        return await response.json()

def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator='\n', strip=True)

async def upload_to_s3(s3, content, bucket, object_name):
    try:
        await s3.put_object(Body=content, Bucket=bucket, Key=object_name)
        logger.info(f"File successfully uploaded: {object_name}")
    except Exception as e:
        logger.error(f"Error occurred while uploading file: {e}")

async def process_job(year):
    logger.info(f"Processing year: {year}")
    progress = get_progress(year)
    
    if not progress:
        logger.warning(f"No progress data found for year {year}")
        update_year_status(year, "pending")
        return

    start_number = progress.get('where_it_left_off')
    end_number = progress.get('end')
    current_page = progress.get('page', 1)

    if start_number is None or end_number is None:
        logger.error(f"Invalid progress data for year {year}: {progress}")
        update_year_status(year, "pending")
        return

    async with aiohttp.ClientSession() as session:
        async with aioboto3.Session().client('s3',
                                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY) as s3:
            try:
                while start_number <= end_number:
                    batch_end = min(start_number + 99, end_number)
                    logger.info(f"Processing batch for year {year}: {start_number} to {batch_end}")
                    
                    search_results = await search_records(session, year, start_number, batch_end, current_page)
                    
                    if not search_results:
                        logger.error(f"No search results returned for year {year}")
                        break

                    data = search_results.get('data', {})
                    if not data:
                        logger.error(f"No 'data' field in search results for year {year}")
                        break

                    records = data.get('data')
                    if not records:
                        logger.info(f"No more results for year {year} in range {start_number} to {batch_end}")
                        start_number = batch_end + 1
                        current_page = 1
                        continue

                    tasks = []
                    for record in records:
                        doc_id = record.get('id')
                        esas_no = record.get('esasNo')
                        karar_no = record.get('kararNo')
                        
                        if doc_id and esas_no and karar_no:
                            task = asyncio.create_task(process_document(session, s3, year, doc_id, esas_no, karar_no))
                            tasks.append(task)
                        else:
                            logger.warning(f"Incomplete record data for year {year}: {record}")

                    await asyncio.gather(*tasks)
                    
                    last_processed = int(records[-1]['esasNo'].split('/')[1])
                    start_number = last_processed + 1
                    save_progress(year, current_page, end_number, start_number)

                    current_page += 1
                    await asyncio.sleep(random.uniform(1, 3))  # Add a small delay between requests

                update_year_status(year, "completed")
                logger.info(f"Completed processing for year {year}")
            except Exception as e:
                logger.error(f"Error processing year {year}: {str(e)}")
                update_year_status(year, "pending")  # Reset status to allow retry
async def process_document(session, s3, year, doc_id, esas_no, karar_no):
    file_name = f"{year}/Esas:{esas_no} Karar:{karar_no}.txt"
    
    try:
        # Check if the file already exists in S3
        await s3.head_object(Bucket=AWS_BUCKET_NAME, Key=file_name)
        logger.info(f"File {file_name} already exists in S3, skipping upload")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            # File doesn't exist, proceed with processing and upload
            document = await get_document(session, doc_id)
            text_content = extract_text_from_html(document['data'])
            await upload_to_s3(s3, text_content, AWS_BUCKET_NAME, file_name)
            logger.info(f"Uploaded file {file_name} to S3")
        else:
            # Some other error occurred
            logger.error(f"Error checking S3 for file {file_name}: {str(e)}")
            raise


