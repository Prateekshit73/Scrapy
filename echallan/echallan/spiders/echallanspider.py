import scrapy


class EchallanspiderSpider(scrapy.Spider):
    name = "echallanspider"
    allowed_domains = ["echallan.parivahan.gov.in"]
    start_urls = ["https://echallan.parivahan.gov.in/index/accused-challan"]

    def parse(self, response):
        pass
