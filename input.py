import json
import re
import sys
from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from bs4 import BeautifulSoup
from colorama import Fore, Style


class HeadlessWebScraper(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.app = QApplication(sys.argv)
        self.browser = QWebEngineView()
        self.browser.setPage(self.browser.page())
        self.browser.loadFinished.connect(self.on_load_finished)
        self.browser.load(QUrl(self.url))

    def run(self):
        self.app.exec_()

    def on_load_finished(self):
        self.browser.page().toHtml(self.save_html)

    def save_html(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        pattern = re.compile(r"window\.__INITIAL_STATE__ = ({.*?});", re.MULTILINE | re.DOTALL)
        script_tag = soup.find("script", text=pattern)
        if not script_tag:
            print("Something went wrong not able to see the data")
        match = pattern.search(script_tag.string)
        initial_state_data = match.group(1)
        json_data = json.loads(initial_state_data)
        inAreaResultViews = json_data["model"]["inAreaResultViews"]
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


def get_html_fromyellow():
    app = QApplication(sys.argv)
    query = input("Please enter keyword or name: ")
    if not query:
        print("Program closed")
        return
    url = f"https://www.yellowpages.com.au/search/listings?clue={query}&locationClue=&lat=&lon="
    scraper = HeadlessWebScraper(url)
    scraper.run()
    scraper.hide()
    sys.exit(app.exec_())


if __name__ == '__main__':
    get_html_fromyellow()
