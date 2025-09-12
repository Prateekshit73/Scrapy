import sqlite3
import os

class EchallanPipeline:
    def __init__(self):
        self.db_path = 'echallan.db'
        self.conn = None
        self.cursor = None

    def open_spider(self, spider):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS echallans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT,
                violator_name TEXT,
                dl_rc_number TEXT,
                challan_no TEXT UNIQUE,
                transaction_id TEXT,
                state TEXT,
                department TEXT,
                challan_date TEXT,
                amount TEXT,
                status TEXT,
                payment_source TEXT,
                challan_print TEXT,
                receipt TEXT,
                payment TEXT,
                payment_verify TEXT
            )
        ''')
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO echallans (
                    vehicle_number, violator_name, dl_rc_number, challan_no,
                    transaction_id, state, department, challan_date, amount,
                    status, payment_source, challan_print, receipt, payment, payment_verify
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('vehicle_number'),
                item.get('violator_name'),
                item.get('dl_rc_number'),
                item.get('challan_no'),
                item.get('transaction_id'),
                item.get('state'),
                item.get('department'),
                item.get('challan_date'),
                item.get('amount'),
                item.get('status'),
                item.get('payment_source'),
                item.get('challan_print'),
                item.get('receipt'),
                item.get('payment'),
                item.get('payment_verify')
            ))
            self.conn.commit()
            spider.logger.info(f"Inserted item for challan: {item.get('challan_no')}")
        except sqlite3.Error as e:
            spider.logger.error(f"Database error: {e}")
        return item
