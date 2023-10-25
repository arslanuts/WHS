import json
import re
import sys
import time

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from bs4 import BeautifulSoup
from colorama import Fore, Style
import warnings
import pandas as pd


warnings.filterwarnings("ignore", category=DeprecationWarning)
total_record_counter = 0
scraped_data = []
default_keywords = [
    "Acetaldehyde manufacturing",
    "Acid acetic manufacturing",
    "Acid organic  manufacturing",
    "Activated carbon/charcoal manufacturing",
    "Carbon black manufacturing",
    "Charcoal briquette manufacturing",
    "Citric acid manufacturing",
    "Ethanol manufacturing",
    "Ether manufacturing",
    "Ethylene glycol manufacturing",
    "Extraction and/or distillation of wood and gum",
    "Formaldehyde manufacturing",
    "Glycol manufacturing n.e.c.",
    "Gum chemical manufacturing",
    "Industrial alcohol manufacturing",
    "Lactic acid manufacturing",
    "Lake colour manufacturing",
    "Methanol manufacturing",
    "Organic dye or pigment manufacturing",
    "Tall oil manufacturing",
    "Tanning extract, organic, manufacturing",
    "Turpentine (except mineral turpentine) manufacturing",
    "Vinyl chloride manufacturing",
    "Wood tar manufacturing"

]


class HeadlessWebScraper(QMainWindow):
    def __init__(self, urls):
        super().__init__()
        self.urls = urls
        self.app = QApplication(sys.argv)
        self.browser = QWebEngineView()
        self.browser.setPage(self.browser.page())
        self.browser.loadFinished.connect(self.on_load_finished)
        self.current_url_index = 0

    def load_next_url(self):
        if self.current_url_index < len(self.urls):
            url = QUrl(self.urls[self.current_url_index])
            self.browser.load(url)
            self.current_url_index += 1
        else:
            self.app.quit()

    def run(self):
        self.load_next_url()
        self.app.exec_()

    def on_load_finished(self):
        self.browser.page().toHtml(self.save_html)

    def save_html(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        pattern = re.compile(r"window\.__INITIAL_STATE__ = ({.*?});", re.MULTILINE | re.DOTALL)
        script_tag = soup.find("script", text=pattern)
        if not script_tag:
            print("Something went wrong not able to see the data")
        else:
            match = pattern.search(script_tag.string)
            initial_state_data = match.group(1)
            json_data = json.loads(initial_state_data)
            inAreaResultViews = json_data["model"]["inAreaResultViews"]
            pagination = json_data["model"]["pagination"]
            global total_record_counter
            total_record_counter += pagination['totalResults']
            for bus in inAreaResultViews:
                try:
                    addressView = bus.get("addressView", {})
                    company_info = {
                        "address": addressView.get("asContactCardFormat", ""),
                        "postCode": addressView.get("postCode", ""),
                        "state": addressView.get("state", ""),
                        "suburb": addressView.get("suburb", ""),
                        "phone": bus.get("callContactNumber", {}).get("displayValue", ""),
                        "category": bus.get("category").get("name"),
                        "detailsLink": bus.get("detailsLink", ""),
                        "description": bus.get("longDescriptor", ""),
                        "name": bus.get("name", ""),
                        "email": bus.get("primaryEmail", "")
                    }
                    scraped_data.append(company_info)
                    print(Fore.BLUE + "Company Information:")
                    print(Fore.CYAN + f"Address: {company_info['address']}")
                    print(Fore.CYAN + f"PostCode: {company_info['postCode']}")
                    print(Fore.CYAN + f"State: {company_info['state']}")
                    print(Fore.CYAN + f"Suburb: {company_info['suburb']}")
                    print(Fore.CYAN + f"Phone: {company_info['phone']}")
                    print(Fore.CYAN + f"Category: {company_info['category']}")
                    print(Fore.CYAN + f"Details Link: {company_info['detailsLink']}")
                    print(Fore.CYAN + f"Description: {company_info['description']}")
                    print(Fore.CYAN + f"Name: {company_info['name']}")
                    print(Fore.CYAN + f"Email: {company_info['email']}")
                    print(Fore.RESET)
                    print("-" * 30)
                except:
                    continue
        time.sleep(1)
        self.load_next_url()


def get_html_fromyellow():
    search_urls = [
        f"https://www.yellowpages.com.au/search/listings?clue={keyword}&locationClue=New+South+Wales&lat=&lon=" for
        keyword in default_keywords]
    scraper = HeadlessWebScraper(search_urls)
    scraper.run()
    scraper.hide()
    df = pd.DataFrame(scraped_data)
    df.to_csv('yellowpages_data.csv', index=False)
    print("Total Records found:", total_record_counter)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    get_html_fromyellow()

    sys.exit(app.exec_())
