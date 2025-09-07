import scrapy
from bookscraper.items import BookItem
# import random
# from urllib.parse import urlencode

# API_KEY = 'df079156-1232-41f4-994c-955c3924aef4'

# def get_proxy_url(url):
#     payload = {'api_key': API_KEY, 'url': url}
#     proxy_url = 'https://proxy.scrapeops.io/v1/?' + urlencode(payload)
#     return proxy_url

class BookspiderSpider(scrapy.Spider):
    name = "bookspider"
    allowed_domains = ["books.toscrape.com", "proxy.scrapeops.io"]
    start_urls = ["https://books.toscrape.com"]

    # def start_requests(self):
    #     yield scrapy.Request(url = get_proxy_url(self.start_urls[0]), callback = self.parse)

    # user_agent_list = [
    #     'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    # ]

    def parse(self, response):
        books = response.css("article.product_pod")
        for book in books:
            relative_url = book.css("h3 a::attr(href)").get()
            if relative_url is not None:
                if "catalogue" in relative_url:
                    book_page_url = "https://books.toscrape.com/" + relative_url
                else:
                    book_page_url = (
                        "https://books.toscrape.com/catalogue/" + relative_url
                    )
                # yield response.follow(book_page_url, callback=self.parse_page, headers = {"User-Agent": self.user_agent_list[random.randint(0, len(self.user_agent_list) - 1)]})
                # yield response.follow(book_page_url, callback=self.parse_page, meta = {'proxy': 'http://user-asdas3a4545:12345678@gate.smartproxy.com:7000'})
                # yield response.follow(url = get_proxy_url(book_page_url), callback = self.parse_page)
                yield response.follow(book_page_url, callback=self.parse_page)

            next_page = response.css("li.next a::attr(href)").get()
            if next_page is not None:
                if "catalogue" in next_page:
                    next_page_url = "https://books.toscrape.com/" + next_page
                else:
                    next_page_url = "https://books.toscrape.com/catalogue/" + next_page
                # yield response.follow(next_page_url, callback=self.parse, headers = {"User-Agent": self.user_agent_list[random.randint(0, len(self.user_agent_list) - 1)]})
                # yield response.follow(next_page_url, callback=self.parse, meta = {'proxy': 'http://user-asdas3a4545:12345678@gate.smartproxy.com:7000'})
                # yield response.follow(url = get_proxy_url(next_page_url), callback = self.parse)
                yield response.follow(next_page_url, callback=self.parse)

    def parse_page(self, response):
        table_rows = response.css("table tr")
        book_item = BookItem()
        book_item["url"] =  response.url
        book_item["title"] =  response.css(".product_main h1::text").get()
        book_item["product_type"] =  table_rows[1].css("td ::text").get()
        book_item["tax"] =  table_rows[4].css("td ::text").get()
        book_item["description"] =  response.xpath("//div[@id='product_description']/following-sibling::p/text()").get()
        yield book_item
