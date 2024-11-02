from selenium import webdriver
from selenium.webdriver.common.by import By
import gspread
from google.oauth2.service_account import Credentials
from time import sleep
import random
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver import FirefoxOptions
# from openpyxl import Workbook
import datetime
from tempfile import mkdtemp


import json
import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Initialize S3 client
s3_client = boto3.client("s3")


import os

DEBUG = os.getenv("DEBUG")

# Function to take a screenshot and upload it to S3
def capture_screenshot_and_upload(driver, file_name):
    if not DEBUG:
        return
    bucket_name = "autogreens-debug"
    screenshot = driver.get_screenshot_as_png()  # Capture screenshot as binary data
    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_name,
        Body=screenshot,
        ContentType="image/png"
    )
    print(f"Screenshot saved to s3://{bucket_name}/{file_name}")

# Fetch Google API credentials JSON from AWS Secrets Manager
def get_google_credentials():
    secret_name = "my-google-api-credentials"  # Name of your secret in Secrets Manager
    region_name = "eu-west-3"  # AWS region of the Secrets Manager

    # Create a Secrets Manager client
    client = boto3.client("secretsmanager", region_name=region_name)
    
    # Retrieve the secret
    response = client.get_secret_value(SecretId=secret_name)
    
    # Parse the JSON credentials and create credentials object
    secret_json = json.loads(response["SecretString"])
    credentials = service_account.Credentials.from_service_account_info(secret_json)
    return credentials

# Fetch custom configuration from AWS Secrets Manager
def get_autogreens_config():
    secret_name = "autogreens-config"  # Name of your secret in Secrets Manager
    region_name = "eu-west-3"  # AWS region of the Secrets Manager

    # Create a Secrets Manager client
    client = boto3.client("secretsmanager", region_name=region_name)
    
    # Retrieve and parse the secret
    response = client.get_secret_value(SecretId=secret_name)
    config = json.loads(response["SecretString"])  # Assuming this is a JSON object
    return config

# Retrieve Google API credentials and apply scopes
creds = get_google_credentials()
scope = [
   'https://spreadsheets.google.com/feeds',
   'https://www.googleapis.com/auth/spreadsheets',
   'https://www.googleapis.com/auth/drive.file',
   'https://www.googleapis.com/auth/drive'
]
creds = creds.with_scopes(scope)

# Authorize the client
client = gspread.authorize(creds)

# Higher-order functions for Google Sheets operations
def create_row(sheet, data):
   sheet.append_row(data)

def read_data(sheet):
   return sheet.get_all_records()

def update_cell(sheet, row, col, new_value):
    sheet.update_cell(row, col, new_value)

def delete_row(sheet, row):
    sheet.delete_rows(row)

# Constants for column indexes
GREENYARD_PRICE_COL = 4
VP_COL = 7
MARGE_COL = 8
LAST_UPDATE_COL = 9

# Load configuration
config = get_autogreens_config()


# Access the parameters
GY_USERNAME_MARKET = config.get('gy_username_market')
GY_PASSWORD_MARKET = config.get('gy_password_market')


def human_sleep(min_time=1, max_time=3):
   sleep_time = random.uniform(min_time, max_time)
   sleep(sleep_time)




options = webdriver.ChromeOptions()
options.binary_location = '/opt/chrome/chrome'
options.add_argument("--headless=new")
options.add_argument('--no-sandbox')
options.add_argument("--disable-gpu")
#small screen to save memory selenium
options.add_argument("--window-size=800,600")
options.add_argument("--single-process")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-dev-tools")
options.add_argument("--no-zygote")
options.add_argument(f"--user-data-dir={mkdtemp()}")
options.add_argument(f"--data-path={mkdtemp()}")
options.add_argument(f"--disk-cache-dir={mkdtemp()}")
# options.add_argument("--remote-debugging-port=9222")


def init_eos(username, password):
    # Initialize the Chrome driver
   service = webdriver.ChromeService("/opt/chromedriver")
   driver = webdriver.Chrome(options=options, service=service)

   # Step 1: Log in to the website
   driver.get("https://eos.firstinfresh.be/login")
   human_sleep(4, 6)
   print(username, password)

   # Enter username
   username_input = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/form/div[1]/div[1]/input")
   ActionChains(driver).move_to_element(username_input).click().perform()
   human_sleep(2, 3)
   username_input.send_keys(username)  # Replace with your username
   human_sleep(2, 3)
   print("Username entered")

   # Enter password
   password_input = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/form/div[1]/div[2]/input")
   ActionChains(driver).move_to_element(password_input).click().perform()
   human_sleep(2, 3)
   password_input.send_keys(password)  # Replace with your password
   human_sleep(2, 3)
   print("Password entered")

   print(driver.page_source)  # This will print the full HTML of the current page
   capture_screenshot_and_upload(
            driver, "login-page.png"
        )
   
   element_to_remove = driver.find_element(By.XPATH, "/html/body/div[3]")
   driver.execute_script("arguments[0].parentNode.removeChild(arguments[0]);", element_to_remove)
   print("Obstructing element removed.")
    
   # Submit the form
   login_button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/form/div[2]/input")
   ActionChains(driver).move_to_element(login_button).click().perform()
   human_sleep(3, 5)
   print("Logged in successfully")
  
   return driver


import re

def extract_price(input_string):
    # Regular expression to match the price pattern (e.g., "€ 1,79")
    price_pattern = r"€\s*\d+[.,]\d{2}"
    
    # Search for the price in the input string
    match = re.search(price_pattern, input_string)
    
    # Return the price if found, otherwise return None
    return match.group(0) if match else None


def run_eos(username, password, sheet):
    driver = init_eos(username, password)
    capture_screenshot_and_upload(
            driver, "after-init.png"
        )
    data = read_data(sheet)
    i = 2
    for e in data:
        print(e)
        # Step 2: Navigate to the desired page
        driver.get(f"https://eos.firstinfresh.be/shop/item/{e.get('GY-REF')}")
        human_sleep(2, 4)
        print(driver.page_source)  # This will print the full HTML of the current page
        capture_screenshot_and_upload(
            driver, f"item-{e.get('GY-REF')}.png"
        )


        # Step 3: Scrape the required information
        #Try or skip
        
        try:
         vp_data_element = driver.find_element(By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[6]/table/tbody/tr[4]/td[2]")
         scraped_data = vp_data_element.text
         scraped_data = extract_price(scraped_data)
         print(scraped_data)
         update_cell(sheet, i, VP_COL, scraped_data)
         data_element = driver.find_element(By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[6]/table/tbody/tr[2]/td[2]")
         scraped_data = data_element.text
         print(scraped_data)
         update_cell(sheet, i, GREENYARD_PRICE_COL, scraped_data)
         ct = datetime.datetime.now()
         update_cell(sheet, i, LAST_UPDATE_COL, str(ct))
        except:
         print("Error")
         update_cell(sheet, i, GREENYARD_PRICE_COL, "Error")
         
        i+=1


    driver.quit()  





def handler(event, context):
    # SHEET WITH NAME "MARKET" AND "EXPRESS"
    sheet_market = client.open('PRIX-GREENYARD').get_worksheet(0)
    run_eos(GY_USERNAME_MARKET, GY_PASSWORD_MARKET, sheet_market)
    # sheet_express.sort((PRIJS_VERSHIL_COL, 'des'))
    return {
        "statusCode": 200,
        "body": "OK"
    }





