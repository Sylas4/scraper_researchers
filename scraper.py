import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from tqdm import tqdm
import json
import time
import pandas as pd

class ResearchScraper:
    def __init__(self, base_url, domain, chromedriver_path):
        self.base_url = base_url
        self.domain = domain
        self.session = requests.Session()
        self.options = Options()
        self.options.add_argument("--headless")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.121 Safari/537.36")
        self.service = Service(chromedriver_path)
        self.driver = webdriver.Chrome(service=self.service, options=self.options)

    def fetch_page(self, url):
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def fetch_dynamic_page(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.rims-filter-group"))
            )
            return self.driver.page_source
        except (TimeoutException, WebDriverException) as e:
            print(f"Error fetching {url} dynamically: {e}")
            return None

    def get_text_or_default(self, element, default=""):
        return element.get_text(strip=True) if element else default

    def scrape_research_groups(self):
        html = self.fetch_page(self.base_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        subject_groups = []
        for card in soup.select('article.promo.type--link a'):
            subject_groups.append({
                "name": card.get_text(strip=True),
                "link": self.domain + card.get('href')
            })
        return subject_groups

    def scrape_subgroups(self, subject_groups):
        for group in tqdm(subject_groups, desc="Processing Research Groups"):
            html = self.fetch_dynamic_page(group["link"])
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            subgroups = []
            for subgroup in soup.select("div.rims-filter-group a"):
                subgroups.append({
                    "name": subgroup.get_text(strip=True),
                    "link": self.domain + subgroup.get('href')
                })
            group["subgroups"] = subgroups
        return subject_groups

    def scrape_researchers(self, subject_groups):
        for group in tqdm(subject_groups, desc="Processing Subgroups"):
            for subgroup in group.get("subgroups", []):
                html = self.fetch_page(subgroup["link"] + "#tab-staff-and-contact")
                if not html:
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                researchers = []
                for researcher in soup.select("div.profile-card.profile-card--small"):
                    researchers.append({
                        "name": self.get_text_or_default(researcher.select_one("a.profile-card__name")),
                        "title": self.get_text_or_default(researcher.select_one("span.profile-card__title")),
                        "email": self.get_text_or_default(researcher.select_one("div.profile-card__contact a")),
                        "link": researcher.select_one("a.profile-card__name").get("href", "")
                    })
                subgroup["researchers"] = researchers
        return subject_groups

    def save_to_json(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def save_to_excel(self, data, filename):
        flat_data = []
        for group in data:
            for subgroup in group.get("subgroups", []):
                for researcher in subgroup.get("researchers", []):
                    flat_data.append({
                        "research group": group["name"],
                        "subgroup": subgroup["name"],
                        "name": researcher["name"],
                        "title": researcher["title"],
                        "email": researcher["email"],
                        "address": researcher.get("address", "N/A")
                    })
        df = pd.DataFrame(flat_data)
        df.to_excel(filename, index=False, engine="openpyxl")

    def run(self):
        subject_groups = self.scrape_research_groups()
        subject_groups = self.scrape_subgroups(subject_groups)
        subject_groups = self.scrape_researchers(subject_groups)
        self.save_to_json(subject_groups, "data/research_data.json")
        self.save_to_excel(subject_groups, "data/research_data.xlsx")
        self.driver.quit()

if __name__ == "__main__":
    base_url = "https://ki.se/en/research/research-areas-centres-and-networks/research-groups"
    domain = "https://ki.se"
    chromedriver_path = "/usr/local/bin/chromedriver"
    scraper = ResearchScraper(base_url, domain, chromedriver_path)
    scraper.run()
