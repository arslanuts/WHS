import json
import math
import re
import sys
import threading
import time
import pandas as pd
import datetime
from PyQt5.QtCore import QCoreApplication, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from bs4 import BeautifulSoup
from colorama import Fore, Style
import warnings
import requests
import xmltodict
import json
from fake_useragent import UserAgent

warnings.filterwarnings("ignore", category=DeprecationWarning)
scraped_data = []
MaxRecords = 500


class ABRSearcher:
    def __init__(self, authentication_guid):
        self.authentication_guid = authentication_guid
        self.base_url = 'https://abr.business.gov.au/abrxmlsearch/AbrXmlSearch.asmx/ABRSearchByNameAdvancedSimpleProtocol'

    def search_businesses(self, keyword, post_code="", max_results=100):
        businesses = []
        params = {
            'name': keyword,
            'postcode': "",
            'legalName': 'Y',
            'tradingName': 'N',
            'NSW': "Y",
            'SA': 'N',
            'ACT': 'N',
            'VIC': 'N',
            'WA': 'N',
            'NT': 'N',
            'QLD': 'N',
            'TAS': 'N',
            'authenticationGuid': self.authentication_guid,
            'searchWidth': 'narrow',
            'minimumScore': '0',
            'maxSearchResults': max_results}

        try:
            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                data = xmltodict.parse(response.text)
                if 'ABRPayloadSearchResults' in data:
                    search_results = data['ABRPayloadSearchResults']['response']['searchResultsList'][
                        'searchResultsRecord']
                    if not isinstance(search_results, list):
                        search_results = [search_results]
                    for result in search_results:
                        abn = result['ABN']['identifierValue']
                        mainName = result.get('mainName', {})
                        if not mainName:
                            mainName = result.get('businessName', {})
                        name = mainName.get('organisationName', '')
                        if not name:
                            name = result.get('legalName', {}).get('fullName')
                        state = result['mainBusinessPhysicalAddress']['stateCode']
                        postcode = result['mainBusinessPhysicalAddress']['postcode']
                        is_current = result['mainBusinessPhysicalAddress']['isCurrentIndicator'] == 'Y'
                        businesses.append({
                            'ABN': abn,
                            'Name': name,
                            'State': state,
                            'Postcode': postcode,
                            'IsCurrent': is_current
                        })
            else:
                print(f"Request failed with status code {response.status_code}")
        except Exception as e:
            print(f"An error occurred: {e}")
        best_match = None
        best_match_score = 0
        for business in businesses:
            name = business.get("Name", "").replace(" ", "").replace(".", "").lower()
            keyword_normalized = keyword.replace(" ", "").replace(".", "").lower()

            score = 0
            for char in keyword_normalized:
                if char in name:
                    score += 1

            if score >= best_match_score:
                best_match_score = score
                best_match = business
        if best_match:
            return best_match.get("ABN")
        return None


class YellowPagesScraper(QMainWindow):
    def __init__(self, keywords):
        super().__init__()
        self.keywords = keywords
        self.scraped_data = []
        self.browser = QWebEngineView()
        self.browser.setPage(self.browser.page())
        self.browser.loadFinished.connect(self.on_load_finished)
        self.current_keyword_index = 0
        self.pageNumber = 1
        self.total_pages = 1
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.authentication_guid = "3ecee520-acf0-4b47-80f2-25ee15f00bc9"
        self.abr_scraper = ABRSearcher(self.authentication_guid)
        self.user_agent = UserAgent()
        self.threads = []


    def load_next_url(self):
        if self.current_keyword_index < len(self.keywords):
            keyword = self.keywords[self.current_keyword_index]
            url = f"https://www.yellowpages.com.au/search/listings?clue={keyword}&locationClue=New+South+Wales&lat=&lon=&pageNumber={self.pageNumber}"
            if self.pageNumber <= self.total_pages:
                # if self.pageNumber <= self.total_pages:
                url = QUrl(url)
                print(f"Requesting data for '{keyword}' (Page {self.pageNumber}) from server, please wait.")
                self.browser.load(url)
                self.pageNumber += 1
            else:
                self.current_keyword_index += 1
                self.pageNumber = 1
                self.total_pages = 1
                self.load_next_url()
        else:
            self.save_to_csv()

    def run(self):
        self.load_next_url()

    def get_abn_from_yellow(self, link):
        headers = {'User-Agent': self.user_agent.random}
        res = requests.get(link, headers=headers)
        time.sleep(0.1)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            try:
                abn = soup.find("dd", class_="abn").text
            except:
                abn = None
        return abn

    def get_abn_from_abr(self, name, postcode):
        return self.abr_scraper.search_businesses(name, postcode)

    def get_abn_numbers(self, data):
        abn_scraper_data = []
        print(data)
        for obj in data:
            if obj.get("detailsLink"):
                abn = self.get_abn_from_yellow(obj.get("detailsLink"))
                if not abn:
                    abn = self.get_abn_from_abr(obj.get("name"), obj.get("postCode"))
                if abn:
                    obj["abn"] = abn
                    abn_scraper_data.append(obj)
        self.scraped_data.extend(abn_scraper_data)

    def on_load_finished(self):
        self.browser.page().toHtml(self.save_html)

    def save_html(self, html_content):
        _scraped_data = []
        soup = BeautifulSoup(html_content, 'html.parser')
        pattern = re.compile(r"window\.__INITIAL_STATE__ = ({.*?});", re.MULTILINE | re.DOTALL)
        script_tag = soup.find("script", text=pattern)
        if not script_tag:
            print("Something went wrong, not able to see the data")
        else:
            match = pattern.search(script_tag.string)
            initial_state_data = match.group(1)
            json_data = json.loads(initial_state_data)
            inAreaResultViews = json_data["model"]["inAreaResultViews"]
            pagination = json_data["model"]["pagination"]
            if self.total_pages == 1:
                totalResults = pagination['totalResults'] if pagination['totalResults'] < MaxRecords else MaxRecords
                self.total_pages = math.ceil(totalResults / 35)
            for bus in inAreaResultViews:
                try:
                    featuredReview = ""
                    avg_review = bus.get("averageRatings", {})
                    yellow_summery = avg_review.get("yellowReviewSummary", {})
                    searchableAddress = bus.get('searchableAddress', {})
                    if yellow_summery is not None:
                        featuredReview = yellow_summery.get('featuredReview', {}).get("reviewText")
                    addressView = bus.get("addressView", {})
                    company_info = {
                        "address": addressView.get("asContactCardFormat", ""),
                        "postCode": addressView.get("postCode", ""),
                        "state": addressView.get("state", ""),
                        "suburb": addressView.get("suburb", ""),
                        "phone": bus.get("callContactNumber", {}).get("displayValue", ""),
                        "category": bus.get("category").get("name"),
                        "description": bus.get("longDescriptor", ""),
                        "name": bus.get("name", ""),
                        "email": bus.get("primaryEmail", ""),
                        "detailsLink": bus.get("detailsLink", ""),
                        "review": featuredReview,
                        "longitude": searchableAddress.get('longitude', ""),
                        "latitude": searchableAddress.get("latitude", "")
                    }
                    _scraped_data.append(company_info)
                    print(Fore.BLUE + "Company Information:")
                    print(Fore.CYAN + f"Address: {company_info['address']}")
                    print(Fore.CYAN + f"PostCode: {company_info['postCode']}")
                    print(Fore.CYAN + f"State: {company_info['state']}")
                    print(Fore.CYAN + f"Suburb: {company_info['suburb']}")
                    print(Fore.CYAN + f"Phone: {company_info['phone']}")
                    print(Fore.CYAN + f"Category: {company_info['category']}")
                    print(Fore.CYAN + f"Description: {company_info['description']}")
                    print(Fore.CYAN + f"Name: {company_info['name']}")
                    print(Fore.CYAN + f"Email: {company_info['email']}")
                    print(Fore.RESET)
                    print("-" * 30)
                except:
                    continue
        time.sleep(1)
        t = threading.Thread(target=self.get_abn_numbers, args=(_scraped_data,))
        t.start()
        self.threads.append(t)
        self.load_next_url()

    def save_to_csv(self):
        for th in self.threads:
            th.join()
        df = pd.DataFrame(self.scraped_data)
        filename = f"data/yellowpages_data_{self.timestamp}.csv"
        df.to_csv(filename, index=False)
        print(f"All data saved to {filename}")
        self.browser.close()
        QApplication.instance().quit()


def get_from_yellow(keywords):
    app = QApplication(sys.argv)
    authentication_guid = '3ecee520-acf0-4b47-80f2-25ee15f00bc9'
    abr_searcher = ABRSearcher(authentication_guid)
    businesses = abr_searcher.search_businesses(keywords)
    df = pd.DataFrame(businesses)
    keyword_list = df["Name"].tolist()
    scraper = YellowPagesScraper(keywords=keyword_list)
    scraper.run()
    scraper.hide()
    scraped_data = scraper.scraped_data
    # app.quit()
    return scraped_data


def abn_lookup_tool(keyword_list):
    app = QApplication(sys.argv)
    scraper = YellowPagesScraper(keywords=[keyword_list[0]])
    scraper.run()
    # scraper.hide()
    app.quit()
    return scraped_data



class Scraper(QThread):
    def __init__(self, keywords):
        super().__init__()
        self.keywords = keywords

    def run(self):
        app = QApplication([])
        scraper = YellowPagesScraper(keywords=self.keywords)
        scraper.run()
        scraper.hide()
        app.exec_()
