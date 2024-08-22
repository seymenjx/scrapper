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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup, NavigableString, Tag
import re
import os
import boto3
from dotenv import dotenv_values
from alive_progress import alive_bar

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

print(API_KEY)
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
            print("CAPTCHA solving...")
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
        driver.execute_script("arguments[0].style.display = 'block';", recaptcha_response_element)
        
        # Set the CAPTCHA solution
        driver.execute_script(f'arguments[0].value = "{captcha_solution}";', recaptcha_response_element)
        
        # Dispatch the input event
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", recaptcha_response_element)
        
        # Wait for any potential callback to process
        time.sleep(5)
        
        # Check if CAPTCHA is solved (you might need to adjust this based on the website's behavior)
        try:
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".recaptcha-checkbox-unchecked"))
            )
            print("CAPTCHA appears to be solved successfully.")
            driver.refresh()
            return True
        except TimeoutException:
            print("CAPTCHA solution might not have been accepted.")
            return False
        
    except Exception as e:
        print(f"An error occurred while applying the CAPTCHA solution: {str(e)}")
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
    print("CAPTCHA detected, solving...")
    
    try:
        captcha_iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='reCAPTCHA']"))
        )
        driver.switch_to.frame(captcha_iframe)
        print("Switched to CAPTCHA iframe.")

        recaptcha_checkbox = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="recaptcha-anchor"]'))
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
    print("Checking for Captcha ....")
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
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "iframe[title='reCAPTCHA']"))
        )
        print("CAPTCHA iframe is no longer visible.")
    except TimeoutException:
        print("Error: CAPTCHA iframe did not disappear within the expected time.")

def initialize_search(driver, line, hilal):
    try:
        # First, check for CAPTCHA
        if check_captcha(driver):
            print("CAPTCHA handled, proceeding with search initialization.")
        
        # Try to click the drop-down using JavaScript
        drop_down = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='detay']"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", drop_down)
        
        try:
            # Try regular click first
            drop_down.click()
        except ElementClickInterceptedException:
            # If regular click fails, try JavaScript click
            driver.execute_script("arguments[0].click();", drop_down)
        
        time.sleep(1)
        
        search_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "esasNoYil"))
        )
        search_field.clear()
        search_field.send_keys(str(line))

        search_field1 = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="esasNoSira1"]'))
        )
        search_field1.clear()
        search_field1.send_keys("1")

        search_field2 = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="esasNoSira2"]'))
        )
        search_field2.clear()
        search_field2.send_keys("999999")
        search_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="detaylıAramaG"]'))
        )
        
        try:
            # Try regular click first
            search_button.click()
        except ElementClickInterceptedException:
            # If regular click fails, try JavaScript click
            driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(2)

        # Check for CAPTCHA again after search
        if check_captcha(driver):
            print("CAPTCHA handled after search, proceeding.")

        total_results = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "toplamSonuc"))
        )
        # set no of records to 100
        record = driver.find_element(By.XPATH, "//*[@id='detayAramaSonuclar_length']/label/select/option[4]")
        record.click()

        time.sleep(2)

        # navigate to the page to be continued
        page = 1
        while page < hilal:
            element = WebDriverWait(driver, 40).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="detayAramaSonuclar_next"]/a')))
            element.click()
            page += 1
            time.sleep(0.1)

        time.sleep(0.5)
        max_pages = int(total_results.text) // 100 + 1

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', {'id': 'detayAramaSonuclar'})
        if table is None:
            raise NoSuchElementException("Couldn't find table.")

        table_body = table.find('tbody')
        rows = table_body.find_all('tr')
        data = [[ele.text.strip() for ele in row.find_all('td') if ele.text.strip()] for row in rows]

        print(f"{len(data)} Records Selected.")

        time.sleep(0.5)
        
        element_table = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "detayAramaSonuclar"))
        )
        element_table_body = element_table.find_element(By.TAG_NAME, 'tbody')
        element_rows = element_table_body.find_elements(By.TAG_NAME, 'tr')
        
        return max_pages, data, element_rows

    except Exception as e:
        print(f"Error in initialize_search: {str(e)}")
        return None, None, None

def process_line(line, pageurl, start, end):
    print(f"Process started for year {line}")
    driver = setup_driver()

    try:
        driver.get(pageurl)
        human_like_actions(driver)

        hilal = start
        global max_pages
        global data 
        global element_rows
        max_pages, data, element_rows = initialize_search(driver, line, hilal)
        
        # Iterrate through all the pages
        print(max_pages)
        with alive_bar(max_pages,title=f"Worker 1") as bar:
            while hilal <= end:
                try:
                    # Iterrate through all the rows
                    i = 0
                    while i < 100:          
                        try:
                            # Select the row 
                            element_table = driver.find_element(By.ID, "detayAramaSonuclar")
                            element_table_body = element_table.find_element(By.TAG_NAME, 'tbody')
                            element_rows = element_table_body.find_elements(By.TAG_NAME, 'tr')
        
                            element_rows[i].click()
                            time.sleep(0.5)

                            # Scrap the content for that row 
                            html = driver.page_source
                            soup = BeautifulSoup(html, 'html.parser')
                            satirlar = []
                            for br in soup.findAll('br'):
                                next_s = br.nextSibling
                                if not (next_s and isinstance(next_s, NavigableString)):
                                    continue    
                                next2_s = next_s.nextSibling
                                if next2_s and isinstance(next2_s, Tag) and next2_s.name == 'br':
                                    text = str(next_s).strip()
                                    if text:
                                        satirlar.append(next_s)
                            if len(satirlar) == 0:
                                raise Exception("No Content Found, Symptoms of Captcha")
                            file_name = 'Esas:' + data[i][1].replace('/', ' ') + " " + 'Karar:' + data[i][2].replace('/', ' ')
                            sanitized_file_name = sanitize_file_name(file_name)
                            base_path = os.getcwd()
                            output_dir = os.path.join(base_path, 'output')
                            os.makedirs(output_dir, exist_ok=True)
                            with open(os.path.join(output_dir, f'{sanitized_file_name}.txt'), 'w', encoding='utf-8') as esas:
                                for satir in satirlar:
                                    esas.write(satir)
                                    esas.write('\n')
                            print("File Saved: ", file_name + '.txt')

                            # Upload to S3
                            upload_to_s3( os.path.join(output_dir, f'{sanitized_file_name}.txt'), AWS_BUCKET_NAME, f'{sanitized_file_name}.txt')
                            # Remove file from output directory after uploading to S3
                            os.remove(os.path.join(output_dir, f'{sanitized_file_name}.txt'))
                        
                            i += 1
                        except Exception as e:
                            print("Error Occurred: " + str(e))
                            check_captcha(driver)
                            wait_for_captcha_to_disappear(driver)
                            max_pages, data, element_rows = initialize_search(driver, line, hilal)

                    element = WebDriverWait(driver, 40).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="detayAramaSonuclar_next"]/a')))
                    element.click()
                    hilal += 1
                    bar()
                    time.sleep(0.5)
                    # Move to the next page
                    print("Moved to Next Page: " + str(hilal))
                
                except Exception as e:
                    print("Error Occurred: " + str(e))
                    check_captcha(driver)
                    wait_for_captcha_to_disappear(driver)
                    max_pages, data, element_rows = initialize_search(driver, line, hilal)
                
    except Exception as e:
        print("Error Occurred: " + str(e))
        check_captcha(driver)
        wait_for_captcha_to_disappear(driver)
        max_pages, data, element_rows = initialize_search(driver, line, hilal)

    finally:
        driver.quit()



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



input_dir = os.path.join(os.getcwd(), 'input')

pageurl = "https://karararama.yargitay.gov.tr/"
for line in [[2022, 1 , 2448, 999999]]:
    process_line(line[0], pageurl, line[1], line[2])
