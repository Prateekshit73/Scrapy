import scrapy
import requests
import cv2
import pytesseract
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time


class EchallanspiderSpider(scrapy.Spider):
    name = "echallanspider"
    allowed_domains = ["echallan.parivahan.gov.in"]
    start_urls = ["https://echallan.parivahan.gov.in/index/accused-challan"]

    def parse(self, response):
        # Read challan numbers from file
        with open("challan_numbers.txt", "r") as f:
            challan_numbers = [line.strip() for line in f if line.strip()]

        for accused_challan_no in challan_numbers:
            self.logger.info(f"Processing challan number: {accused_challan_no}")

            # Step 1: Download captcha image
            captcha_url = "https://echallan.parivahan.gov.in/index/captcha-login?rand=438.7520329174046"
            r = requests.get(captcha_url, stream=True)
            img_bytes = BytesIO(r.content)

            # Step 2: Load and preprocess captcha image for OCR
            import numpy as np

            img_pil = Image.open(img_bytes).convert("L")  # grayscale PIL image
            img_np = np.array(img_pil)  # convert to numpy array for OpenCV
            img_resized = cv2.resize(
                img_np, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR
            )
            img_blurred = cv2.medianBlur(img_resized, 3)
            _, img_thresh = cv2.threshold(img_blurred, 150, 255, cv2.THRESH_BINARY)

            # Step 3: OCR to extract captcha text
            text = pytesseract.image_to_string(img_thresh)
            captcha_text = "".join([c for c in text if c.isalnum()])

            self.logger.info(f"Extracted captcha text: {captcha_text}")

            # Step 4: Use Selenium to automate input on the page
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            browser = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()), options=options
            )
            browser.get("https://echallan.parivahan.gov.in/index/accused-challan")

            # Fill accused challan number
            browser.find_element(By.ID, "accused_challan_no").send_keys(
                accused_challan_no
            )

            # Fill captcha text
            browser.find_element(By.ID, "captcha").send_keys(captcha_text)

            # Optionally submit the form if needed
            browser.find_element(By.ID, "btnSearch").click()

            # Wait for some time to observe results or scrape further if needed
            time.sleep(5)

            browser.quit()
