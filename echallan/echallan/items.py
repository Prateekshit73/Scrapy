# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class EchallanItem(scrapy.Item):
    vehicle_number = scrapy.Field()
    violator_name = scrapy.Field()
    dl_rc_number = scrapy.Field()
    challan_no = scrapy.Field()
    transaction_id = scrapy.Field()
    state = scrapy.Field()
    department = scrapy.Field()
    challan_date = scrapy.Field()
    amount = scrapy.Field()
    status = scrapy.Field()
    payment_source = scrapy.Field()
    challan_print = scrapy.Field()
    receipt = scrapy.Field()
    payment = scrapy.Field()
    payment_verify = scrapy.Field()
