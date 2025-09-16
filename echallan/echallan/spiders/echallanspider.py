import scrapy
import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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

api_key_2captcha = os.getenv("APIKEY_2CAPTCHA")
scrapeops_api_key = os.getenv("SCRAPEOPS_API_KEY")
solver = TwoCaptcha(api_key_2captcha)


class EchallanspiderSpider(scrapy.Spider):
    name = "echallanspider"
    allowed_domains = ["echallan.parivahan.gov.in"]
    start_urls = ["https://echallan.parivahan.gov.in/index/accused-challan"]

    def parse(self, response):
        try:
            with open("vehical_numbers.txt", "r") as f:
                vehicle_numbers = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(
                "Missing 'vehical_numbers.txt'. Create it with vehicle numbers, one per line."
            )
            return

        if not vehicle_numbers:
            self.logger.warning("No vehicle numbers to process; spider closing early.")
            return

        for vehicle_number in vehicle_numbers:
            self.logger.info(f"Processing {vehicle_number}")

            # Fetch random user-agent from ScrapeOps
            scrapeops_url = "https://headers.scrapeops.io/v1/user-agents"
            params = {"api_key": scrapeops_api_key}
            resp = requests.get(scrapeops_url, params=params)
            if resp.status_code == 200:
                user_agents = resp.json().get("result", [])
                random_user_agent = (
                    user_agents[0]
                    if user_agents
                    else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            else:
                random_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")  # Mitigate transient window flash
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-notifications")  # Suppress GCM errors
            options.add_argument("--log-level=3")  # Minimize console noise
            options.add_argument("--disable-images")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--no-first-run")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f"--user-agent={random_user_agent}")
            options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

            browser = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options,
            )
            browser.execute_cdp_cmd("Network.enable", {})
            browser.get("https://echallan.parivahan.gov.in/index/accused-challan")

            try:
                # Fetch initial randomSalt from verify-detail
                self.logger.info("Fetching initial randomSalt")
                browser.get("https://echallan.parivahan.gov.in/index/verify-detail")
                response_json = None
                logs = browser.get_log("performance")
                for entry in logs:
                    log = json.loads(entry["message"])["message"]
                    if (
                        log["method"] == "Network.responseReceived"
                        and "verify-detail" in log["params"]["response"]["url"]
                    ):
                        request_id = log["params"]["requestId"]
                        try:
                            resp = browser.execute_cdp_cmd(
                                "Network.getResponseBody", {"requestId": request_id}
                            )
                            body = resp.get("body", "")
                            if resp.get("base64Encoded", False):
                                import base64

                                body = base64.b64decode(body).decode("utf-8")
                            response_json = json.loads(body)
                            break
                        except Exception as e:
                            self.logger.error(
                                f"Error getting verify-detail response: {e}"
                            )

                initial_salt = (
                    response_json.get("token", str(time.time()))
                    if response_json
                    else str(time.time())
                )
                self.logger.info(f"Initial randomSalt fetched: {initial_salt}")

                # Navigate back to main form page
                self.logger.info("Loading main form page")
                browser.get("https://echallan.parivahan.gov.in/index/accused-challan")
                WebDriverWait(browser, 10).until(
                    lambda d: d.execute_script("return document.readyState")
                    == "complete"
                )
                time.sleep(3)  # Angular init buffer

                # Read live randomSalt from hidden input
                random_salt = browser.execute_script(
                    "return document.getElementById('randomSalt').value;"
                )
                self.logger.info(f"Live randomSalt from page: {random_salt}")

                # Select Vehicle Number via label click
                self.logger.info("Selecting vehicle radio via label")
                label = WebDriverWait(browser, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//label[contains(@for, 'rc_number_new')]")
                    )
                )
                label.click()
                self.logger.info("Vehicle radio label clicked")

                # Wait for input visibility
                time.sleep(2)
                self.logger.info("Waiting for input visibility post-radio select")

                # Enter vehicle number
                WebDriverWait(browser, 15).until(
                    EC.visibility_of_element_located((By.ID, "rc_no"))
                )
                WebDriverWait(browser, 15).until(
                    EC.element_to_be_clickable((By.ID, "rc_no"))
                )
                input_field = browser.find_element(By.ID, "rc_no")
                input_field.clear()
                input_field.send_keys(vehicle_number.upper())
                self.logger.info(f"Entered vehicle number: {vehicle_number}")

                captcha_passed = False
                attempts = 0
                max_attempts = 3
                img_path = "captcha.png"

                while not captcha_passed and attempts < max_attempts:
                    attempts += 1
                    self.logger.info(f"Attempt {attempts}: Starting CAPTCHA solve")

                    try:
                        # Wait for CAPTCHA image
                        img_element = WebDriverWait(browser, 15).until(
                            EC.presence_of_element_located((By.ID, "captchaimg"))
                        )
                        self.logger.info("CAPTCHA image loaded")
                    except TimeoutException:
                        self.logger.warning(
                            f"No CAPTCHA image for {vehicle_number}; skipping (invalid format/site error)"
                        )
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        browser.quit()
                        break

                    # Extract src and rand
                    img_src = img_element.get_attribute("src")
                    self.logger.info(f"CAPTCHA src: {img_src}")
                    rand = (
                        img_src.split("rand=")[1].split("&")[0]
                        if "rand=" in img_src
                        else str(time.time())
                    )
                    self.logger.info(f"CAPTCHA rand param: {rand}")

                    # Download CAPTCHA image
                    start_solve = time.time()
                    captcha_url = f"https://echallan.parivahan.gov.in/index/captcha-login?rand={rand}"
                    r = requests.get(captcha_url, stream=True)
                    with open(img_path, "wb") as f:
                        f.write(r.content)
                    self.logger.info(
                        f"CAPTCHA image downloaded in {time.time() - start_solve:.2f}s"
                    )

                    try:
                        # Solve CAPTCHA
                        solve_start = time.time()
                        result = solver.normal(img_path)
                        solve_time = time.time() - solve_start
                        captcha_text = result["code"]
                        self.logger.info(
                            f"CAPTCHA solved in {solve_time:.2f}s: {captcha_text}"
                        )

                        # Input CAPTCHA text
                        captcha_input = browser.find_element(By.ID, "captcha")
                        captcha_input.clear()
                        captcha_input.send_keys(captcha_text)
                        self.logger.info("CAPTCHA text inputted")

                        # Submit form
                        submit_start = time.time()
                        button = browser.find_element(By.ID, "btnSearch")
                        browser.execute_script(
                            "arguments[0].click();", button
                        )  # JS click to avoid interception
                        self.logger.info(
                            f"Form submitted in {time.time() - submit_start:.2f}s"
                        )

                        # Wait for response
                        time.sleep(7)  # Increased to 7s for server response
                        self.logger.info("Waiting for submit response")

                        # Check for error modal
                        try:
                            modal = WebDriverWait(browser, 10).until(
                                EC.presence_of_element_located(
                                    (By.CLASS_NAME, "swal2-modal")
                                )
                            )
                            self.logger.error("CAPTCHA failed: Error modal detected")
                            browser.save_screenshot(f"error_{vehicle_number}.png")
                            # Log modal content
                            modal_content = browser.find_element(
                                By.ID, "modalContentId"
                            ).text
                            self.logger.info(f"Modal content: {modal_content}")
                            # Retry clicking OK button
                            max_retries = 3
                            for retry in range(max_retries):
                                try:
                                    ok_button = browser.find_element(
                                        By.CLASS_NAME, "swal2-confirm"
                                    )
                                    self.logger.info(
                                        f"OK button found, attempt {retry + 1}"
                                    )
                                    browser.execute_script(
                                        "arguments[0].click();", ok_button
                                    )
                                    self.logger.info("Modal dismissed via JS click")
                                    break
                                except Exception as e:
                                    self.logger.warning(
                                        f"Retry {retry + 1}/{max_retries} to dismiss modal: {e}"
                                    )
                                    time.sleep(1)
                            else:
                                self.logger.error(
                                    "Failed to dismiss modal after retries"
                                )
                            browser.execute_script("refreshCaptcha();")
                            time.sleep(0.5)  # Reduced post-refresh delay
                            self.logger.info("CAPTCHA refreshed for retry")
                            if os.path.exists(img_path):
                                os.remove(img_path)
                            continue  # Retry
                        except TimeoutException:
                            # No modal: Check for success button
                            try:
                                total_button = WebDriverWait(browser, 5).until(
                                    EC.presence_of_element_located(
                                        (
                                            By.CSS_SELECTOR,
                                            "button.btn.btn-primary.ng-binding",
                                        )
                                    )
                                )
                                button_text = total_button.text
                                self.logger.info(
                                    f"SUCCESS: Total Challan button found - {button_text}"
                                )
                                if "Total Challan" in button_text:
                                    challan_count = (
                                        button_text.split(":")[1].strip()
                                        if ":" in button_text
                                        else "Unknown"
                                    )
                                    self.logger.info(
                                        f"Verified {challan_count} challans via button"
                                    )
                                    captcha_passed = True
                            except TimeoutException:
                                self.logger.error(
                                    "No success button after submit - checking API"
                                )
                                # Fallback to check API status
                                logs = browser.get_log("performance")
                                for entry in reversed(logs):
                                    try:
                                        log = json.loads(entry["message"])["message"]
                                        if (
                                            "api/get-challan-detail"
                                            in log["params"]["response"]["url"]
                                        ):
                                            request_id = log["params"]["requestId"]
                                            resp = browser.execute_cdp_cmd(
                                                "Network.getResponseBody",
                                                {"requestId": request_id},
                                            )
                                            body = resp.get("body", "")
                                            if resp.get("base64Encoded", False):
                                                import base64

                                                body = base64.b64decode(body).decode(
                                                    "utf-8"
                                                )
                                            api_response = json.loads(body)
                                            self.logger.info(
                                                f"API response status: {api_response.get('status')}"
                                            )
                                            if api_response.get("status") == "Success":
                                                self.logger.info(
                                                    "API success detected via fallback"
                                                )
                                                captcha_passed = True
                                            break
                                    except Exception as e:
                                        self.logger.warning(f"API fallback error: {e}")
                                if not captcha_passed:
                                    browser.execute_script("refreshCaptcha();")
                                    time.sleep(0.5)
                                    if os.path.exists(img_path):
                                        os.remove(img_path)
                                    continue
                    except Exception as e:
                        self.logger.error(f"2CAPTCHA or submission error: {e}")
                        browser.save_screenshot(f"error_{vehicle_number}.png")
                        browser.execute_script("refreshCaptcha();")
                        time.sleep(0.5)
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        continue

                if os.path.exists(img_path):
                    os.remove(img_path)

                if not captcha_passed:
                    self.logger.error(
                        f"Failed to solve CAPTCHA after {max_attempts} attempts for {vehicle_number}"
                    )
                    continue

                self.logger.info("CAPTCHA verified successful - capturing API")

                # Re-read randomSalt post-submit
                random_salt = browser.execute_script(
                    "return document.getElementById('randomSalt').value;"
                )
                self.logger.info(f"Post-submit randomSalt: {random_salt}")

                # Capture API response
                response_json = None
                logs = browser.get_log("performance")
                for entry in reversed(logs):
                    try:
                        log = json.loads(entry["message"])["message"]
                    except json.JSONDecodeError:
                        continue
                    if (
                        log["method"] == "Network.responseReceived"
                        and "api/get-challan-detail" in log["params"]["response"]["url"]
                        and random_salt in log["params"]["response"]["url"]
                    ):
                        request_id = log["params"]["requestId"]
                        try:
                            resp = browser.execute_cdp_cmd(
                                "Network.getResponseBody", {"requestId": request_id}
                            )
                            body = resp.get("body", "")
                            if resp.get("base64Encoded", False):
                                import base64

                                body = base64.b64decode(body).decode("utf-8")
                            response_json = json.loads(body)
                            self.logger.info("Captured API response successfully")
                            break
                        except Exception as e:
                            self.logger.warning(
                                f"Could not retrieve body for request {request_id}: {e}"
                            )
                            continue

                # Log current URL
                current_url = browser.current_url
                self.logger.debug(f"Current URL after submission: {current_url}")

                if response_json and response_json.get("status") == "Success":
                    results = response_json.get("results", [])
                    self.logger.info(
                        f"Found {len(results)} challan results for {vehicle_number}"
                    )
                    for result in results:
                        item = EchallanItem()
                        item["vehicle_number"] = vehicle_number
                        item["accused_name"] = result.get("accused_name", "")
                        item["accused_father_name"] = result.get(
                            "accused_father_name", ""
                        )
                        item["owner_name"] = result.get("owner_name", "")
                        item["doc_no"] = result.get("doc_no", "")
                        item["challan_no"] = result.get("challan_no", "")
                        item["date_time"] = result.get("date_time", "")
                        item["amount"] = str(result.get("amount", ""))
                        item["challan_status"] = result.get("challan_status", "")
                        item["payment_source"] = result.get("payment_source", "")
                        item["pdf_url"] = result.get("pdf_url", "")
                        item["receipt_url"] = result.get("receipt_url", "")
                        item["state_code"] = result.get("state_code", "")
                        item["office_name"] = result.get("office_name", "")
                        item["area_name"] = result.get("area_name", "")
                        item["office_text"] = result.get("office_text", "")
                        item["offences"] = result.get("offences", [])
                        item["under_investigate"] = result.get(
                            "under_investigate", False
                        )
                        item["vehicle_class"] = result.get("vehicle_class", "")
                        item["transaction_id"] = result.get("transaction_id", "")
                        item["payment_date"] = result.get("payment_date", "")
                        item["lat_long"] = result.get("lat_long", "")
                        item["officer_id"] = str(result.get("officer_id", ""))
                        item["designation"] = result.get("designation", "")
                        item["status_txt"] = result.get("status_txt", "")
                        yield item
                else:
                    api_status = (
                        response_json.get("status", "Unknown")
                        if response_json
                        else "No API response"
                    )
                    self.logger.info(
                        f"No challan details found or API error ({api_status}) for {vehicle_number}"
                    )

            except Exception as e:
                self.logger.error(f"Error processing {vehicle_number}: {str(e)}")
                browser.save_screenshot(f"error_{vehicle_number}.png")

            finally:
                browser.quit()
                time.sleep(1)  # Inter-vehicle delay
