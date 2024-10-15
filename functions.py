import redis
import json
import os
import ssl
from urllib.parse import urlparse
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
import time
import random
import requests
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from bs4 import BeautifulSoup, NavigableString, Tag
import re
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import dotenv_values
from alive_progress import alive_bar
from selenium.webdriver.common.action_chains import ActionChains
import traceback
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Redis URL from environment variable
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

# Update other functions to use get_redis_connection() instead of a global redis_client


# Load .env.local values and update the os.environ dictionary
config = {
    **dotenv_values(".env.local"),
    **os.environ,
}

# Update os.environ with the values from config
os.environ.update(config)

API_KEY = os.getenv("API_KEY")  # 2Captcha API key
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")


# For testing
# def setup_driver():
#     ua = UserAgent()
#     user_agent = ua.random
#     print(f"Kullanıcı Ajanı: {user_agent}")
#     options = Options()
#     options.add_argument(f'--user-agent={user_agent}')
#     options.add_argument('--ignore-certificate-errors')
#     options.add_argument('--ignore-ssl-errors')
#     options.add_argument('--disable-web-security')
#     path = "/Users/griffinannshuals/.wdm/drivers/chromedriver/mac64/127.0.6533.99/chromedriver-mac-arm64/chromedriver"
#     service = Service(executable_path=path)
#     driver = webdriver.Chrome(service=service, options=options)
#     return driver


# Production Code
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def solve_captcha(driver, sitekey, pageurl):
    try:
        response = requests.post("http://2captcha.com/in.php", data={
            'key': API_KEY,
            'method': 'userrecaptcha',
            'googlekey': sitekey,
            'pageurl': pageurl,
            'json': 1
        }, timeout=30)
        response.raise_for_status()
        request_id = response.json().get('request')
        if not request_id:
            raise ValueError("Failed to get request ID from 2captcha")
        return request_id
    except requests.RequestException as e:
        print(f"Error sending CAPTCHA solve request: {str(e)}")
        return None


def get_captcha_solution(request_id):
    max_attempts = 30  # 5 minutes max
    attempt = 0
    while attempt < max_attempts:
        try:
            url = f"http://2captcha.com/res.php?key={API_KEY}&action=get&id={request_id}&json=1"    
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get('status') == 1:
                return result.get('request')
            elif 'CAPCHA_NOT_READY' not in result.get('request', ''):
                print(f"Unexpected response: {result}")
                return None
            print("CAPTCHA solving >>")
        except requests.RequestException as e:
            print(f"Error getting CAPTCHA solution: {str(e)}")

        attempt += 1
        time.sleep(10)

    print("Max attempts reached. CAPTCHA solving failed.")
    return None


def apply_captcha_solution(driver, captcha_solution):
    try:
        driver.switch_to.default_content()

        # Wait for the recaptcha response element to be present
        recaptcha_response_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "g-recaptcha-response"))
        )

        # Make the element visible
        driver.execute_script(
            "arguments[0].style.display = 'block';", recaptcha_response_element)

        # Set the CAPTCHA solution
        driver.execute_script(f'arguments[0].value = "{captcha_solution}";', recaptcha_response_element)

        # Dispatch the input event
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", recaptcha_response_element)

        # Wait for any potential callback to process
        time.sleep(5)

        # Check if CAPTCHA is solved (you might need to adjust this based on the website's behavior)
        try:
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".recaptcha-checkbox-unchecked"))
            )
            print("CAPTCHA appears to be solved successfully.")
            driver.refresh()
            return True
        except TimeoutException:
            print("CAPTCHA solution might not have been accepted.")
            return False

    except Exception as e:
        print(
            f"An error occurred while applying the CAPTCHA solution: {str(e)}")
        return False


def human_like_actions(driver):
    time.sleep(random.uniform(1, 3))
    body = driver.find_element(By.TAG_NAME, 'body')
    body.click()
    time.sleep(random.uniform(1, 3))


def sanitize_file_name(file_name):
    # Remove invalid characters from the file name
    file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
    return file_name


def close_captcha_iframe(driver):
    try:
        driver.execute_script("""
            var iframes = document.querySelectorAll('iframe[title="reCAPTCHA"]');
            iframes.forEach(function(iframe) {
                if (iframe && iframe.parentNode) iframe.parentNode.removeChild(iframe);
            });
        """)
        print("CAPTCHA iframes removed.")
    except Exception as e:
        print(f"Error: Unable to remove CAPTCHA iframes. {str(e)}")


def process_captcha(driver, sitekey, pageurl):
    print("CAPTCHA detected, solving >>")

    try:
        captcha_iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[title='reCAPTCHA']"))
        )
        driver.switch_to.frame(captcha_iframe)
        print("Switched to CAPTCHA iframe.")

        recaptcha_checkbox = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="recaptcha-anchor"]'))
        )
        recaptcha_checkbox.click()
        print("CAPTCHA checkbox clicked.")

        driver.switch_to.default_content()

        request_id = solve_captcha(driver, sitekey, pageurl)
        if not request_id:
            return False

        captcha_solution = get_captcha_solution(request_id)
        if not captcha_solution:
            return False

        result = apply_captcha_solution(driver, captcha_solution)

        close_captcha_iframe(driver)
        time.sleep(2)
        return result

    except Exception as e:
        print(f"Error during CAPTCHA processing: {str(e)}")
        return False


def check_captcha(driver):
    print("Checking for Captcha >>>")
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            is_display_captcha_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "g-recaptcha"))
            )
            sitekey = is_display_captcha_element.get_attribute('data-sitekey')

            if is_display_captcha_element and sitekey:
                driver.refresh()
                result = process_captcha(driver, sitekey, driver.current_url)
                if result:
                    print("Captcha Solved!")
                    return True
                else:
                    print(f"CAPTCHA solving attempt {attempt + 1} failed. Retrying...")
            else:
                print("No CAPTCHA detected.")
                return False
        except TimeoutException:
            print("No CAPTCHA detected.")
            return False
        except Exception as e:
            print(f"Error checking for CAPTCHA: {str(e)}")

        time.sleep(2)

    print("Failed to solve CAPTCHA after maximum attempts.")
    return False


def wait_for_captcha_to_disappear(driver):
    try:
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, "iframe[title='reCAPTCHA']"))
        )
        print("CAPTCHA iframe is no longer visible.")
    except TimeoutException:
        print("Error: CAPTCHA iframe did not disappear within the expected time.")


def extract_lines(driver):
    # Wait for the content to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Get the page source and parse it with BeautifulSoup
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    satirlar = []

    # Find all <br> tags
    for br in soup.findAll('br'):
        next_s = br.nextSibling
        if next_s and isinstance(next_s, NavigableString):
            next2_s = next_s.nextSibling
            if next2_s and isinstance(next2_s, Tag) and next2_s.name == 'br':
                text = str(next_s).strip()
                if text:
                    satirlar.append(text)  # Append the text content

    return satirlar


def initialize_search(driver, line, start_number, finish_number):
    try:
        logging.info(f"Initializing search for year: {line}, start number: {start_number}, finish number: {finish_number}")

        # Handle CAPTCHA if it appears
        if check_captcha(driver):
            print("CAPTCHA handled, proceeding with search initialization.")
            logging.info("CAPTCHA handled during search initialization.")

        # Scroll to the drop-down and try to click it
        drop_down = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='detay']"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", drop_down)

        # Attempt to click the drop-down
        try:
            drop_down.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", drop_down)

        time.sleep(1)

        # Fill out the search fields
        search_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "esasNoYil"))
        )
        search_field.clear()
        search_field.send_keys(str(line))

        search_field1 = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="esasNoSira1"]'))
        )
        search_field1.clear()
        search_field1.send_keys(str(start_number))

        search_field2 = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="esasNoSira2"]'))
        )
        search_field2.clear()
        search_field2.send_keys(str(finish_number))

        # Attempt to click the search button
        search_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="detaylıAramaG"]'))
        )
        try:
            search_button.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", search_button)

        time.sleep(2)

        # Check for CAPTCHA again after search
        if check_captcha(driver):
            print("CAPTCHA handled after search, proceeding.")

        # Wait for the results to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "detayAramaSonuclar"))
        )

        # Set number of records to 100
        try:
            record = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//*[@id='detayAramaSonuclar_length']/label/select/option[4]"))
            )
            record.click()
            time.sleep(2)
        except Exception as e:
            logging.warning(f"Failed to set number of records to 100: {str(e)}")

        # Fetch and process the table data
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', {'id': 'detayAramaSonuclar'})
        if table is None:
            raise NoSuchElementException("Couldn't find the results table.")

        table_body = table.find('tbody')
        rows = table_body.find_all('tr')
        data = [[ele.text.strip() for ele in row.find_all('td') if ele.text.strip()] for row in rows]

        total_results_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "toplamSonuc"))
        )
        total_results = int(total_results_element.text)
        max_pages = (total_results - 1) // 100 + 1

        logging.info(f"{len(data)} Records selected on this page. Total results: {total_results}")
        print(f"{len(data)} Records Selected. Total results: {total_results}")

        return max_pages, data

    except Exception as e:
        error_message = traceback.format_exc()
        logging.error(f"Error in initialize_search: {error_message}")
        print(f"Error in initialize_search: {str(e)}")

        if check_captcha(driver):
            wait_for_captcha_to_disappear(driver)

        return None, None

def get_progress(year):
    redis_client = get_redis_connection()
    progress = redis_client.hget('scraping_progress', str(year))
    if progress:
        return json.loads(progress)
    return None

def save_progress(year, page, begin, start, end, start_number, status='in_progress'):
    progress = json.dumps({
        'page': page,
        'begin': begin,
        'start': start,
        'end': end,
        'start_number': start_number,
        'status': status
    })
    redis_client = get_redis_connection()
    redis_client.hset('scraping_progress', str(year), progress)

def get_next_year():
    redis_client = get_redis_connection()
    logger.info("Attempting to get next year from Redis")
    try:
        all_years = redis_client.hgetall('scraping_progress')
        logger.info(f"Retrieved {len(all_years)} years from Redis")
        for year, data_str in all_years.items():
            data = json.loads(data_str)
            if data['status'] == 'pending':
                year_int = int(year.decode('utf-8'))
                logger.info(f"Found pending year: {year_int}")
                return year_int
        logger.info("No pending years found")
        return None
    except Exception as e:
        logger.error(f"Error in get_next_year: {str(e)}")
        return None

def process_line(line, pageurl, start, end, start_number):
    logging.info(f"Process started for year {line}")
    print(f"Process started for year {line}")
    driver = setup_driver()
    s3_client = boto3.client('s3',
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    try:
        driver.get(pageurl)
        human_like_actions(driver)

        # Retrieve progress from Redis
        progress = get_progress(line)
        hilal = progress['page']
        begin = progress['begin']

        global g_max_pages, c_max_pages, data
        g_max_pages, data = initialize_search(driver, line, begin, end)
        if g_max_pages is None or data is None:
            raise Exception("Failed to initialize search")
        c_max_pages = g_max_pages
        
        with alive_bar(g_max_pages, title=f"Processing year: {line}") as bar:
            while True:
                try:
                    if not data or len(data) == 0:
                        max_pages, data = initialize_search(driver, line, begin, end)
                        if max_pages is None or data is None:
                            raise Exception("Failed to initialize search")

                    element_table = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.ID, "detayAramaSonuclar"))
                    )
                    element_table_body = element_table.find_element(By.TAG_NAME, 'tbody')
                    element_rows = element_table_body.find_elements(By.TAG_NAME, 'tr')

                    for i, row in enumerate(element_rows):
                        max_retries = 3
                        for retry in range(max_retries):
                            try:
                                #did change the reading first record
                                esas_number = int(data[i][1].split('/')[1])
                                begin = esas_number

                                expected_file_name = f'Esas:{data[i][1].replace("/", " ")} Karar:{data[i][2].replace("/", " ")}'
                                sanitized_expected_file_name = sanitize_file_name(expected_file_name)
                                s3_key = f'{sanitized_expected_file_name}.txt'

                                driver.implicitly_wait(10)
                                ActionChains(driver).move_to_element(row).click(row).perform()

                                time.sleep(0.5)
                                satirlar = extract_lines(driver)

                                if verify_content_matches_filename(satirlar, sanitized_expected_file_name, s3_client, AWS_BUCKET_NAME):
                                    print(f"Content matches for file: {s3_key}. No action needed.")
                                else:
                                    print(f"Content mismatch for file: {s3_key}. Deleting old file and uploading new one.")
                                    try:
                                        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
                                        print(f"Deleted old file from S3: {s3_key}")
                                    except s3_client.exceptions.NoSuchKey:
                                        print(f"No existing file to delete in S3: {s3_key}")
                                
                                # Upload the new content
                                base_path = os.getcwd()
                                output_dir = os.path.join(base_path, 'output')
                                os.makedirs(output_dir, exist_ok=True)

                                file_path = os.path.join(output_dir, s3_key)
                                with open(file_path, 'w', encoding='utf-8') as esas:
                                    for satir in satirlar:
                                        esas.write(satir)
                                        esas.write('\n')

                                print(f"Uploading new file to S3: {s3_key}")
                                upload_to_s3(file_path, AWS_BUCKET_NAME, s3_key)
                                os.remove(file_path)

                                # Save progress to Redis
                                save_progress(line, hilal, begin, start, end, start_number)
                                
                                break  # If successful, break the retry loop
                            except StaleElementReferenceException:
                                if retry < max_retries - 1:
                                    print(f"Stale element, retrying ({retry + 1}/{max_retries})...")
                                    # Refresh the elements
                                    element_table = WebDriverWait(driver, 20).until(
                                        EC.presence_of_element_located((By.ID, "detayAramaSonuclar"))
                                    )
                                    element_table_body = element_table.find_element(By.TAG_NAME, 'tbody')
                                    element_rows = element_table_body.find_elements(By.TAG_NAME, 'tr')
                                    row = element_rows[i]  # Get the updated row
                                else:
                                    raise  # If max retries reached, raise the exception

                    # Move to the next page
                    element = WebDriverWait(driver, 40).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="detayAramaSonuclar_next"]/a')))
                    element.click()
                    hilal += 1
                    bar()
                    print("Moved to Next Page: " + str(hilal))

                except Exception as e:
                    print("Error Occurred: " + str(e))
                    check_captcha(driver)
                    wait_for_captcha_to_disappear(driver)
                    c_max_pages, data = initialize_search(driver, line, begin, end)
                    hilal = 1

    except Exception as e:
        print(f"Error processing year {line}: {str(e)}")
        # Set the year's status back to pending
        progress = get_progress(line)
        if progress:
            progress['status'] = 'pending'
            save_progress(line, **progress)
        raise  # Re-raise the exception to be caught by the main loop
    finally:
        driver.quit()
        if begin > end:
            # Mark the year as completed when done
            save_progress(line, 1, 1, start, end, start_number, status='completed')
        else:
            # Save the current progress
            save_progress(line, hilal, begin, start, end, start_number)


def verify_content_matches_filename(new_content, expected_filename, s3_client, bucket_name):
    s3_key = f'{expected_filename}.txt'
    
    try:
        # Attempt to get the object from S3
        existing_file = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        existing_content = existing_file['Body'].read().decode('utf-8')
        
        # Normalize the new content to a string if it's a list
        new_content_str = '\n'.join(new_content) if isinstance(new_content, list) else new_content
        
        # Compare the existing content with the new content
        if existing_content.strip() == new_content_str.strip():
            print(f"Content matches for file: {s3_key}")
            return True
        else:
            print(f"Content mismatch for file: {s3_key}")
            return False
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            # If the file doesn't exist in S3, we consider it a mismatch
            print(f"File does not exist in S3: {s3_key}")
            return False
        else:
            # For any other error, we raise the exception
            raise

def upload_to_s3(file_path, bucket, object_name):

    s3_client = boto3.client('s3',
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    try:
        # Check if the object already exists in the bucket
        s3_client.head_object(Bucket=bucket, Key=object_name)
        print(f"File already exists in S3: {object_name}. Skipping upload.")
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            # Object does not exist, proceed with upload
            try:
                s3_client.upload_file(file_path, bucket, object_name)
                print(f"File successfully uploaded: {file_path}")

            except Exception as e:
                print(f"Error occurred while uploading file: {e}")
        else:
            # Something else has gone wrong.
            print(f"Error checking if file exists: {e}")

def check_redis_connection():
    try:
        redis_client = get_redis_connection()
        redis_client.ping()
        print("Successfully connected to Redis")
        return True
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        return False

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Specify the version of ChromeDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager(version="114.0.5735.90").install()), options=chrome_options)
    return driver