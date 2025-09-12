import scrapy
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import sys
from dotenv import load_dotenv
from twocaptcha import TwoCaptcha
from ..items import EchallanItem

# Load environment variables from .env file
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


api_key = os.getenv("APIKEY_2CAPTCHA")
solver = TwoCaptcha(api_key)


class EchallanspiderSpider(scrapy.Spider):
    name = "echallanspider"
    allowed_domains = ["echallan.parivahan.gov.in"]
    start_urls = ["https://echallan.parivahan.gov.in/index/accused-challan"]

    def parse(self, response):
        with open("vehical_numbers.txt", "r") as f:
            vehical_numbers = [line.strip() for line in f if line.strip()]

        for accused_challan_no in vehical_numbers:
            self.logger.info(f"Processing {accused_challan_no}")

            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            browser = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()), options=options
            )
            browser.get("https://echallan.parivahan.gov.in/index/accused-challan")

            captcha_passed = False
            self.logger.info("Trying 2captcha")
            img_element = browser.find_element(By.ID, "captchaimg")
            img_src = img_element.get_attribute("src")
            rand = img_src.split("rand=")[1]
            captcha_url = (
                f"https://echallan.parivahan.gov.in/index/captcha-login?rand={rand}"
            )
            r = requests.get(captcha_url, stream=True)
            img_path = "captcha.png"
            with open(img_path, "wb") as f:
                f.write(r.content)
            try:
                result = solver.normal(img_path)
                captcha_text = result["code"]
                browser.find_element(By.ID, "captcha").clear()
                browser.find_element(By.ID, "captcha").send_keys(captcha_text)
                browser.find_element(By.ID, "btnSearch").click()
                time.sleep(3)
                try:
                    browser.find_element(By.CLASS_NAME, "swal2-modal")
                    self.logger.error("2captcha failed")
                    captcha_passed = False
                except Exception:
                    captcha_passed = True
            except Exception as e:
                self.logger.error(f"2captcha error: {e}")
                captcha_passed = False

            if not captcha_passed:
                browser.quit()
                continue

            # Wait for the table rows to load
            try:
                WebDriverWait(browser, 10).until(
                    EC.presence_of_element_located((By.ID, "lists"))
                )
                self.logger.info("Table rows loaded")
                table = browser.find_element(By.ID, "my-table")
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                self.logger.info(f"Found {len(rows)} rows in table")
                for row in rows:
                    tds = row.find_elements(By.TAG_NAME, "td")
                    if len(tds) == 14:
                        self.logger.info("Processing row with 14 columns")
                        item = EchallanItem()
                        item["vehicle_number"] = accused_challan_no
                        item["violator_name"] = tds[0].text.strip()
                        item["dl_rc_number"] = tds[1].text.strip()
                        item["challan_no"] = tds[2].text.strip()
                        item["transaction_id"] = tds[3].text.strip()
                        item["state"] = tds[4].text.strip()
                        item["department"] = tds[5].text.strip()
                        item["challan_date"] = tds[6].text.strip()
                        item["amount"] = tds[7].text.strip()
                        item["status"] = tds[8].text.strip()
                        item["payment_source"] = tds[9].text.strip()
                        # Challan Print
                        try:
                            link = tds[10].find_element(By.TAG_NAME, "a")
                            item["challan_print"] = link.get_attribute("href")
                        except Exception:
                            item["challan_print"] = tds[10].text.strip()
                        # Receipt
                        try:
                            link = tds[11].find_element(By.TAG_NAME, "a")
                            item["receipt"] = link.get_attribute("href")
                        except Exception:
                            item["receipt"] = tds[11].text.strip()
                        item["payment"] = tds[12].text.strip()
                        item["payment_verify"] = tds[13].text.strip()
                        self.logger.info(
                            f"Yielding item for challan: {item['challan_no']}"
                        )
                        yield item
                    else:
                        self.logger.warning(f"Row has {len(tds)} columns, expected 14")
            except Exception as e:
                self.logger.error(f"Error waiting for table or processing rows: {e}")
                self.logger.info(f"No table found for vehicle: {accused_challan_no}")

            browser.quit()
