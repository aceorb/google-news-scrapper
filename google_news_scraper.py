# -*- encoding: utf-8 -*-
import os
import random
import re
import shutil
import time
import uuid
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from create_db_v3 import create_table_query, db_config
from captchasolver import CaptchaSolver

proxy_list = [
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9000",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9001",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9002",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9003",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9004",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9005",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9006",
    "http://kjX8BJ4vZeQkaOVj:wifi;us;@proxy.soax.com:9007"
]

driver_exec_path = "/usr/bin/chromedriver"
max_retries = 3

def multiWait(driver, locators, max_polls, output_type):
    print('===== WebDriver-MultiWait =====')
    print(f'[MultiWait] Locators: {locators}')
    print(f"[MultiWait] Max-Polls: {max_polls}")
    wait = WebDriverWait(driver, 1)
    cp = 0
    while cp < max_polls:
        cp += 1
        for i, loc in enumerate(locators):
            if isinstance(loc, dict):
                func = loc.get('func')
                if func is not None:
                    fargs = loc.get('args', ())
                    fkwds = loc.get('kwargs', {})
                    if func(*fargs, **fkwds):
                        return i
                    time.sleep(1)
                else:
                    ec = loc.get('ec', EC.presence_of_element_located(loc.get('locator')))
                    methods = loc.get('methods')
                    try:
                        element = wait.until(ec)
                        print(f"[MultiWait] Element found at {loc.get('locator')}")
                        if methods is not None:
                            print(f"[MultiWait] {loc.get('locator')} - Methods: {methods}")
                            if not all([eval(f"element.{m}()", {'element': element}) for m in methods]):
                                raise TimeoutException
                        print(f"[MultiWait] All methods exist on {loc.get('locator')}")
                        return i if output_type == 'id' else element
                    except TimeoutException:
                        pass
            else:
                if callable(loc):
                    if loc():
                        return i
                    time.sleep(1)
                else:
                    try:
                        element = wait.until(EC.presence_of_element_located(loc))
                        print(f'[MultiWait] Element found at {loc}')
                        return i if output_type == 'id' else element
                    except TimeoutException:
                        pass
        print(f"[MultiWait] Current-Polls: {cp}")

def create_driver(chrome_options, max_retries=3):
    for attempt in range(max_retries):
        try:
            chrome_service = Service(executable_path=driver_exec_path)
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
            return driver
        except WebDriverException as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                print(f"Failed to create WebDriver after {max_retries} attempts")
                raise
            time.sleep(5)  # Wait before retrying

def google_news_search(query, start_date, end_date, proxy_extension_dir):
    global max_retries

    if max_retries == 0:
        return []
    max_retries -= 1

    base_url = 'https://www.google.com/search?q={query}&tbs=cdr:1,cd_min:{start_date},cd_max:{end_date}&tbm=nws'
    search_url = base_url.format(query=query, start_date=start_date, end_date=end_date)

    chrome_options = Options()
    chrome_options.binary_location = '/usr/bin/google-chrome-stable'
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")

    driver = None
    articles = []
    try:
        driver = create_driver(chrome_options)
        
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)

        driver.get("https://api.ipify.org?format=text")
        ip_address = driver.find_element(By.TAG_NAME, "body").text
        print(f"WebDriver is running on IP: {ip_address}")

        driver.get(search_url)

        locs = [
            (By.XPATH, '//*[@class="MjjYud"]'),
            (By.XPATH, '//iframe[@title="reCAPTCHA"]')
        ]
        r = multiWait(driver, locs, max_polls=30, output_type='id')
        if r == 1:
            print("Captcha detected, bypassing ...")
            CaptchaSolver(
                driver=driver,
                image_getting_method='request',
                response_locator=(By.XPATH, '//*[@class="MjjYud"]')
            ).setCaptchaTypeAsRecaptchaV2().solve()
            print("Captcha bypassed!")
            time.sleep(5)
            if 'sorry' in driver.current_url:
                driver.get(search_url)
            r = multiWait(driver, locs, max_polls=30, output_type='id')
            if r == 1:
                raise Exception("IP is blocked")

        page_count = 0

        while page_count < 4:  # Limit to 3 pages
            page_count += 1
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            search_results = soup.find_all('div', class_='SoaBEf')

            if not search_results:
                print("No search results found on the page")
                break

            print(f"Found {len(search_results)} search results on page {page_count}")

            for result in search_results:
                title = result.find('div', attrs={'role': 'heading'}).text if result.find('div', attrs={'role': 'heading'}) else "No title found"
                url = result.find('a')['href'] if result.find('a') else "No URL found"
                body_element = result.find('div', class_='GI74Re nDgy9d')
                body = body_element.text if body_element else "No body text found"
                date_element = result.find('div', class_='OSrXXb rbYSKb LfVVr')
                date = date_element.find('span').text if date_element and date_element.find('span') else "No date found"
                
                articles.append({'title': title, 'url': url, 'body': body, 'date': date, 'term': query})

            if page_count < 3:  # Don't look for next page on the last iteration
                next_button = driver.find_elements(By.XPATH, "//a[@id='pnnext']")
                if next_button and next_button[0].is_displayed() and len(search_results) == 10:
                    print(f"Clicking on the next page button (page {page_count + 1})")
                    next_button[0].click()
                    time.sleep(2)

                    locs = [
                        (By.XPATH, '//*[@class="MjjYud"]'),
                        (By.XPATH, '//iframe[@title="reCAPTCHA"]')
                    ]
                    r = multiWait(driver, locs, max_polls=30, output_type='id')
                    if r == 1:
                        print("IP blocked.")
                        break
                else:
                    print("No more pages found")
                    break
            else:
                print("Reached maximum number of pages (3)")

    except Exception as e:
        print(f"Unexpected exception: {str(e)}")
        if driver:
            driver.quit()
        shutil.rmtree(proxy_extension_dir, ignore_errors=True)
        return google_news_search(query, start_date, end_date, proxy_extension_dir)

    finally:
        if driver:
            driver.quit()

    return articles

def parse_ago_format(date_str):
    now = datetime.now()
    pattern = r"(\d+)\s+(\w+)\s+ago"
    match = re.match(pattern, date_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2).lower()
        if unit in ["hour", "hours"]:
            return now - timedelta(hours=value)
        elif unit in ["day", "days"]:
            return now - timedelta(days=value)
        elif unit in ["week", "weeks"]:
            return now - timedelta(weeks=value)
        elif unit in ["month", "months"]:
            return now - timedelta(days=value * 30)
        elif unit in ["year", "years"]:
            return now - timedelta(days=value * 365)
    return None

company_names = ["Apple", "Microsoft", "Amazon", "Google", "Berkshire Hathaway", "Facebook", "Tesla", "Nvidia",
                 "JPMorgan Chase", "Visa", "Procter & Gamble", "UnitedHealth Group", "Home Depot",
                 "Mastercard", "Bank of America", "Disney", "Comcast", "Pfizer", "Adobe", "Netflix", "Cisco", "Merck", "PepsiCo",
                 "Thermo Fisher Scientific", "Costco", "Broadcom", "Abbott Laboratories", "Accenture", "Danaher", "Medtronic",
                 "Coca-Cola", "Verizon", "Eli Lilly", "Salesforce", "McDonald's", "Qualcomm", "Honeywell", "Goldman Sachs",
                 "Amgen", "NextEra Energy", "Lowe's", "Boeing", "Union Pacific", "Intel", "United Parcel Service",
                 "Texas Instruments", "Starbucks", "Lockheed Martin", "Intuit", "Caterpillar",

     "Oracle", "Walmart", "Chevron", "Exxon Mobil", "Wells Fargo", "AT&T", "Citigroup", "Morgan Stanley", 
    "Bristol-Myers Squibb", "BlackRock", "Charles Schwab", "Raytheon Technologies", "3M", "American Express", 
    "T-Mobile", "General Electric", "Target", "American Tower", "Booking Holdings", "CVS Health", "Anthem", 
    "S&P Global", "Gilead Sciences", "TJX Companies", "Linde", "Fidelity National Information Services", 
    "Altria Group", "ConocoPhillips", "Chubb", "Mondelez International", "Colgate-Palmolive", "Marsh & McLennan", 
    "U.S. Bancorp", "Automatic Data Processing", "Crown Castle International", "Becton Dickinson", "Cigna", 
    "Duke Energy", "Zoetis", "Fiserv", "General Motors", "Stryker", "Analog Devices", "Southern Company", 
    "Dominion Energy", "Regeneron Pharmaceuticals", "Vertex Pharmaceuticals", "Intercontinental Exchange", 
    "Activision Blizzard", "Prologis", "Intuitive Surgical", "Estee Lauder", "Micron Technology", 
    "General Dynamics", "FedEx", "Northrop Grumman", "Emerson Electric", "Illinois Tool Works", 
    "Deere & Company", "EOG Resources", "Sherwin-Williams", "Waste Management", "Progressive", "Dow", 
    "Air Products and Chemicals", "Truist Financial", "CSX", "Humana", "Aon", "Edwards Lifesciences", "Biogen", 
    "CME Group", "Ecolab", "Norfolk Southern", "PNC Financial Services", "Synopsys", "Chipotle Mexican Grill", 
    "Marriott International", "Corteva", "Kimberly-Clark", "Allstate", "Autodesk", "Uber Technologies", 
    "Moody's Corporation", "Capital One Financial", "Nucor", "Rockwell Automation", "Constellation Brands", 
    "Marathon Petroleum", "TE Connectivity", "Illumina", "Amphenol", "Kraft Heinz", "Valero Energy", "DuPont", 
    "Sysco", "Public Storage", "Motorola Solutions", "Welltower", "Roper Technologies", "Kinder Morgan", 
    "Dollar General", "Williams Companies", "Xcel Energy", "Archer-Daniels-Midland", "Eaton Corporation", 
    "Ford Motor", "Paychex", "Realty Income", "Simon Property Group", "Aflac", "Electronic Arts", "Ross Stores", 
    "PACCAR", "Freeport-McMoRan", "IDEXX Laboratories", "TransDigm Group", "Monster Beverage", "Newmont", 
    "Halliburton", "Hilton Worldwide", "Fortinet", "VeriSign", "Hershey", "Ball Corporation", "Ingersoll Rand", 
    "Kroger", "Yum! Brands", "Xilinx", "Cintas", "ResMed", "Aptiv", "Align Technology", "Fastenal", 
    "Copart", "O'Reilly Automotive", "Verisk Analytics", "Keysight Technologies", "DexCom", "MSCI", 
    "Mettler-Toledo International", "Hologic", "Arthur J. Gallagher", "Vulcan Materials", "Trane Technologies", 
    "Dover Corporation", "Agilent Technologies", "DaVita", "NXP Semiconductors", "Centene", "IQVIA Holdings", 
    "Fortive", "SVB Financial Group", "Cadence Design Systems", "ANSYS", "Garmin", "Arista Networks", 
    "West Pharmaceutical Services", "Tractor Supply Company", "Northern Trust", "WEC Energy Group", 
    "Carrier Global", "Otis Worldwide", "Digital Realty Trust", "Weyerhaeuser", "McCormick & Company", 
    "Ameren", "Tyson Foods", "PPG Industries", "Hormel Foods", "Consolidated Edison", "Parker-Hannifin", 

    "Willis Towers Watson", "Cummins", "Maxim Integrated Products", "Wayfair", "Teradyne", "Cboe Global Markets", 
    "Masco", "Expeditors International", "Synchrony Financial", "Skyworks Solutions", "Zebra Technologies", 
    "Tyler Technologies", "MarketAxess Holdings", "Universal Health Services", "Eastman Chemical", "J.B. Hunt Transport Services", 
    "Diamondback Energy", "Discover Financial Services", "CenterPoint Energy", "AmerisourceBergen", "Omnicom Group", 
    "Ametek", "L3Harris Technologies", "Ventas", "Microchip Technology", "CBRE Group", "Atmos Energy", 
    "International Flavors & Fragrances", "Best Buy", "Carnival Corporation", "Laboratory Corporation of America", 
    "Regions Financial", "M&T Bank", "State Street Corporation", "Darden Restaurants", "Cabot Oil & Gas", 
    "Genuine Parts Company", "DTE Energy", "Cardinal Health", "Wynn Resorts", "NetApp", "Ulta Beauty", 
    "Advance Auto Parts", "Extra Space Storage", "BorgWarner", "Edison International", "W.W. Grainger", 
    "Pentair", "SBA Communications", "Hess Corporation", "LKQ Corporation", "Hartford Financial Services", 
    "Expedia Group", "United Airlines Holdings", "Southwest Airlines", "Brown-Forman", "Allegion", 
    "Conagra Brands", "First Republic Bank", "Everest Re Group", "Citrix Systems", "Apache Corporation", 
    "CF Industries Holdings", "Iron Mountain", "Federal Realty Investment Trust", "Mosaic Company", 
    "Robert Half International", "F5 Networks", "FLIR Systems", "Vornado Realty Trust", "KeyCorp", 
    "Molson Coors Beverage Company", "Take-Two Interactive", "Evergy", "Comerica", "Leggett & Platt", 
    "NiSource", "Kimco Realty", "Marathon Oil", "PVH Corp", "Citizens Financial Group", "FMC Corporation", 
    "Interpublic Group", "Cincinnati Financial", "Juniper Networks", "Western Digital", "Loews Corporation", 
    "Jack Henry & Associates", "DENTSPLY SIRONA", "Snap-on", "AES Corporation", "Sealed Air", "Rollins", 
    "PPL Corporation", "Huntington Bancshares", "Ralph Lauren", "Regency Centers", "Boston Properties", 
    "American Airlines Group", "NRG Energy", "Pinnacle West Capital", "Devon Energy", "Healthpeak Properties", 
    "Viatris", "Campbell Soup", "Whirlpool Corporation", "Kohl's", "Hasbro", "Newell Brands", "Etsy", 
    "Quanta Services", "ABIOMED", "Trimble", "Qorvo", "Gartner", "EPAM Systems", "Incyte", 
    "Paycom Software", "FactSet Research Systems", "Assurant", "ServiceNow", "Workday", "Splunk", 
    "Roku", "Square", "Twilio", "Zendesk", "CrowdStrike Holdings", "DocuSign", 
    "Zoom Video Communications", "Cloudflare", "Slack Technologies", "RingCentral", 
    "Chewy", "Pinterest", "Spotify Technology", "Shopify", "Atlassian", "Unity Software", "Palantir Technologies", 
    "DoorDash", "Airbnb", "Coupa Software", "ZoomInfo Technologies", "Bill.com Holdings", "Fastly", 
    "MongoDB", "Okta", "Veeva Systems", "HubSpot", "Elastic", "Alteryx", "Avalara", "Five9", "Ceridian HCM Holding", "Dropbox", 
    "Guidewire Software", "New Relic", "Snowflake", "Robinhood Markets", "Coinbase Global", "UiPath", "Toast", "Roblox Corporation", "AppLovin", 
    "Marqeta", "Affirm Holdings", "ContextLogic", "Oscar Health", "Coupang", "Didi Global", "Playtika Holding", 
    "Bumble", "ThredUp", "Blend Labs", "Compass", "ACV Auctions", "Coursera", "Certara", "C3.ai", 
    "Qualtrics International", "Procore Technologies", "Samsara", "Freshworks", "ForgeRock", "Amplitude", 
    "Warby Parker", "Rent the Runway", "Allbirds", "Sweetgreen", "Duolingo", "Braze", "HashiCorp", 

    "Expensify", "Udemy", "Gitlab", "Remitly Global", "Thoughtworks Holding", "Couchbase", 
    "WalkMe", "Integral Ad Science Holding", "Sprinklr", "Frontier Group Holdings", "Compass Pathways", 
    "Recursion Pharmaceuticals", "Zymergen", "Ginkgo Bioworks Holdings", "23andMe Holding", "Beam Therapeutics", 
    "Sana Biotechnology", "Lyell Immunopharma", "Seer", "Berkeley Lights", "Nuvei Corporation", "Global-e Online", 
    "Payoneer Global", "Flywire", "Alkami Technology", "Squarespace", "DigitalOcean Holdings", 
    "Informatica", "Confluent", "Cvent Holding", "Momentive Global", "Similarweb", "ZipRecruiter", 
    "Vimeo", "IronSource", "Skillz", "Olo", "Instacart", "Stripe", "Plaid", "Chime", "Klarna", "Nubank", "Revolut", "SoFi Technologies", 
    "Upstart Holdings", "Lemonade", "Root", "Metromile", "Clover Health Investments", "Hippo Holdings", 
    "Doma Holdings", "Matterport", "Porch Group", "Opendoor Technologies", "Offerpad Solutions", "View", 
    "Desktop Metal", "Butterfly Network", "Luminar Technologies", "Velodyne Lidar", "Ouster", "Aeva Technologies", 
    "Innoviz Technologies", "Cerence", "BigCommerce Holdings", "Dynatrace", "Sumo Logic", 
    "Talend", "Yext", "Box", "Smartsheet", "Asana", "Monday.com", 
    "nCino", "Duck Creek Technologies", "Workiva", "Anaplan", "Zuora", 
    "BlackLine", "Jamf Holding", "SailPoint Technologies Holdings", "Ping Identity Holding", 
    "CyberArk Software", "Qualys", "Rapid7", "Tenable Holdings", "Varonis Systems", "SolarWinds", 
    "Mimecast", "Proofpoint", "Zscaler", "Palo Alto Networks", "Datadog", 
    "Akamai Technologies", "Ciena", "Lumentum Holdings", "II-VI", "Coherent", "IPG Photonics", "Viavi Solutions", "Infinera", 
    "MACOM Technology Solutions Holdings", "Inphi", "MaxLinear", "Semtech", "Lattice Semiconductor", 
    "Monolithic Power Systems", "Power Integrations", "Silicon Laboratories", "Cirrus Logic", 
    "Knowles", "Synaptics", "Universal Display", "Cree", "Acuity Brands", "Hubbell", "Rexnord", 
    "Generac Holdings", "Flowserve", "Nordson", "IDEX", "Graco", "Donaldson Company", "Cognex", 
    "Teledyne Technologies", "Vontier"


]

ai_search_terms = [
    "{} generative AI products",
    "{} artificial intelligence",
    "{} AI",
    "{} AI investment",
    "{} ai partnerships",
]

search_terms = []
for company_name in company_names:
    for ai_term in ai_search_terms:
        search_term = ai_term.format(company_name)
        search_terms.append(search_term)


symbol_mapping = {"Apple": "AAPL", "Microsoft": "MSFT", "Amazon": "AMZN", "Google": "GOOGL",
                  "Berkshire Hathaway": "BRK.A", "Facebook": "META", "Tesla": "TSLA", "Nvidia": "NVDA", "JPMorgan Chase": "JPM",
                  "Visa": "V", "Procter & Gamble": "PG", "UnitedHealth Group": "UNH",
                  "Home Depot": "HD", "Mastercard": "MA", "Bank of America": "BAC", "Disney": "DIS", "Comcast": "CMCSA",
                  "Pfizer": "PFE", "Adobe": "ADBE", "Netflix": "NFLX", "Cisco": "CSCO", "Merck": "MRK", "PepsiCo": "PEP",
                  "Thermo Fisher Scientific": "TMO", "Costco": "COST", "Broadcom": "AVGO", "Abbott Laboratories": "ABT",
                  "Accenture": "ACN", "Danaher": "DHR", "Medtronic": "MDT", "Coca-Cola": "KO", "Verizon": "VZ",
                  "Eli Lilly": "LLY", "Salesforce": "CRM", "McDonald's": "MCD", "Qualcomm": "QCOM", "Honeywell": "HON",
                  "Goldman Sachs": "GS", "Amgen": "AMGN", "NextEra Energy": "NEE", "Lowe's": "LOW", "Boeing": "BA",
                  "Union Pacific": "UNP", "Intel": "INTC", "United Parcel Service": "UPS", "Texas Instruments": "TXN",
                  "Starbucks": "SBUX", "Lockheed Martin": "LMT", "Intuit": "INTU", "Caterpillar": "CAT",

    "Oracle": "ORCL", "Walmart": "WMT", "Chevron": "CVX", "Exxon Mobil": "XOM", "Wells Fargo": "WFC",
    "AT&T": "T", "Citigroup": "C", "Morgan Stanley": "MS", "Bristol-Myers Squibb": "BMY", "BlackRock": "BLK",
    "Charles Schwab": "SCHW", "Raytheon Technologies": "RTX", "3M": "MMM", "American Express": "AXP",
    "T-Mobile": "TMUS", "General Electric": "GE", "Target": "TGT", "American Tower": "AMT",
    "Booking Holdings": "BKNG", "CVS Health": "CVS", "Anthem": "ANTM", "S&P Global": "SPGI",
    "Gilead Sciences": "GILD", "TJX Companies": "TJX", "Linde": "LIN",
    "Fidelity National Information Services": "FIS", "Altria Group": "MO", "ConocoPhillips": "COP",
    "Chubb": "CB", "Mondelez International": "MDLZ", "Colgate-Palmolive": "CL", "Marsh & McLennan": "MMC",
    "U.S. Bancorp": "USB", "Automatic Data Processing": "ADP", "Crown Castle International": "CCI",
    "Becton Dickinson": "BDX", "Cigna": "CI", "Duke Energy": "DUK", "Zoetis": "ZTS", "Fiserv": "FISV",
    "General Motors": "GM", "Stryker": "SYK", "Analog Devices": "ADI", "Southern Company": "SO",
    "Dominion Energy": "D", "Regeneron Pharmaceuticals": "REGN", "Vertex Pharmaceuticals": "VRTX",
    "Intercontinental Exchange": "ICE", "Activision Blizzard": "ATVI", "Prologis": "PLD",
    "Intuitive Surgical": "ISRG", "Estee Lauder": "EL", "Micron Technology": "MU",
    "General Dynamics": "GD", "FedEx": "FDX", "Northrop Grumman": "NOC", "Emerson Electric": "EMR",
    "Illinois Tool Works": "ITW", "Deere & Company": "DE", "EOG Resources": "EOG",
    "Sherwin-Williams": "SHW", "Waste Management": "WM", "Progressive": "PGR", "Dow": "DOW",
    "Air Products and Chemicals": "APD", "Truist Financial": "TFC", "CSX": "CSX", "Humana": "HUM",
    "Aon": "AON", "Edwards Lifesciences": "EW", "Biogen": "BIIB", "CME Group": "CME", "Ecolab": "ECL",
    "Norfolk Southern": "NSC", "PNC Financial Services": "PNC", "Synopsys": "SNPS",
    "Chipotle Mexican Grill": "CMG", "Marriott International": "MAR", "Corteva": "CTVA",
    "Kimberly-Clark": "KMB", "Allstate": "ALL", "Autodesk": "ADSK", "Uber Technologies": "UBER",
    "Moody's Corporation": "MCO", "Capital One Financial": "COF", "Nucor": "NUE",
    "Rockwell Automation": "ROK", "Constellation Brands": "STZ", "Marathon Petroleum": "MPC",
    "TE Connectivity": "TEL", "Illumina": "ILMN", "Amphenol": "APH", "Kraft Heinz": "KHC",
    "Valero Energy": "VLO", "DuPont": "DD", "Sysco": "SYY", "Public Storage": "PSA",
    "Motorola Solutions": "MSI", "Welltower": "WELL", "Roper Technologies": "ROP",
    "Kinder Morgan": "KMI", "Dollar General": "DG", "Williams Companies": "WMB", "Xcel Energy": "XEL",
    "Archer-Daniels-Midland": "ADM", "Eaton Corporation": "ETN", "Ford Motor": "F", "Paychex": "PAYX",
    "Realty Income": "O", "Simon Property Group": "SPG", "Aflac": "AFL", "Electronic Arts": "EA",

    "Ross Stores": "ROST", "PACCAR": "PCAR", "Freeport-McMoRan": "FCX", "IDEXX Laboratories": "IDXX",
    "TransDigm Group": "TDG", "Monster Beverage": "MNST", "Newmont": "NEM", "Halliburton": "HAL",
    "Hilton Worldwide": "HLT", "Fortinet": "FTNT", "VeriSign": "VRSN", "Hershey": "HSY",
    "Ball Corporation": "BLL", "Ingersoll Rand": "IR", "Kroger": "KR", "Yum! Brands": "YUM",
    "Xilinx": "XLNX", "Cintas": "CTAS", "ResMed": "RMD", "Aptiv": "APTV", "Align Technology": "ALGN",
    "Fastenal": "FAST", "Copart": "CPRT", "O'Reilly Automotive": "ORLY", "Verisk Analytics": "VRSK",
    "Keysight Technologies": "KEYS", "DexCom": "DXCM", "MSCI": "MSCI",
    "Mettler-Toledo International": "MTD", "Hologic": "HOLX", "Arthur J. Gallagher": "AJG",
    "Vulcan Materials": "VMC", "Trane Technologies": "TT", "Dover Corporation": "DOV",
    "Agilent Technologies": "A", "DaVita": "DVA", "NXP Semiconductors": "NXPI", "Centene": "CNC",
    "IQVIA Holdings": "IQV", "Fortive": "FTV", "SVB Financial Group": "SIVB",
    "Cadence Design Systems": "CDNS", "ANSYS": "ANSS", "Garmin": "GRMN", "Arista Networks": "ANET",
    "West Pharmaceutical Services": "WST", "Tractor Supply Company": "TSCO", "Northern Trust": "NTRS",
    "WEC Energy Group": "WEC", "Carrier Global": "CARR", "Otis Worldwide": "OTIS",
    "Digital Realty Trust": "DLR", "Weyerhaeuser": "WY", "McCormick & Company": "MKC",
    "Ameren": "AEE", "Tyson Foods": "TSN", "PPG Industries": "PPG", "Hormel Foods": "HRL",
    "Consolidated Edison": "ED", "Parker-Hannifin": "PH", "Willis Towers Watson": "WLTW",
    "Cummins": "CMI", "Maxim Integrated Products": "MXIM", "Wayfair": "W", "Teradyne": "TER",
    "Cboe Global Markets": "CBOE", "Masco": "MAS", "Expeditors International": "EXPD",
    "Synchrony Financial": "SYF", "Skyworks Solutions": "SWKS", "Zebra Technologies": "ZBRA",
    "Tyler Technologies": "TYL", "MarketAxess Holdings": "MKTX", "Universal Health Services": "UHS",
    "Eastman Chemical": "EMN", "J.B. Hunt Transport Services": "JBHT", "Diamondback Energy": "FANG",
    "Discover Financial Services": "DFS", "CenterPoint Energy": "CNP", "AmerisourceBergen": "ABC",
    "Omnicom Group": "OMC", "Ametek": "AME", "L3Harris Technologies": "LHX", "Ventas": "VTR",
    "Microchip Technology": "MCHP", "CBRE Group": "CBRE", "Atmos Energy": "ATO",
    "International Flavors & Fragrances": "IFF", "Best Buy": "BBY", "Carnival Corporation": "CCL",
    "Laboratory Corporation of America": "LH", "Regions Financial": "RF", "M&T Bank": "MTB",
    "State Street Corporation": "STT", "Darden Restaurants": "DRI", "Cabot Oil & Gas": "COG",
    "Genuine Parts Company": "GPC", "DTE Energy": "DTE", "Cardinal Health": "CAH",
    "Wynn Resorts": "WYNN", "NetApp": "NTAP", "Ulta Beauty": "ULTA", "Advance Auto Parts": "AAP",
    "Extra Space Storage": "EXR", "BorgWarner": "BWA", "Edison International": "EIX",
    "W.W. Grainger": "GWW", "Pentair": "PNR", "SBA Communications": "SBAC", "Hess Corporation": "HES",


    "LKQ Corporation": "LKQ", "Hartford Financial Services": "HIG", "Expedia Group": "EXPE",
    "United Airlines Holdings": "UAL", "Southwest Airlines": "LUV", "Brown-Forman": "BF.B",
    "Allegion": "ALLE", "Conagra Brands": "CAG", "First Republic Bank": "FRC",
    "Everest Re Group": "RE", "Citrix Systems": "CTXS", "Apache Corporation": "APA",
    "CF Industries Holdings": "CF", "Iron Mountain": "IRM", "Federal Realty Investment Trust": "FRT",
    "Mosaic Company": "MOS", "Robert Half International": "RHI", "F5 Networks": "FFIV",
    "FLIR Systems": "FLIR", "Vornado Realty Trust": "VNO", "KeyCorp": "KEY",
    "Molson Coors Beverage Company": "TAP", "Take-Two Interactive": "TTWO", "Evergy": "EVRG",
    "Comerica": "CMA", "Leggett & Platt": "LEG", "NiSource": "NI", "Kimco Realty": "KIM",
    "Marathon Oil": "MRO", "PVH Corp": "PVH", "Citizens Financial Group": "CFG",
    "FMC Corporation": "FMC", "Interpublic Group": "IPG", "Cincinnati Financial": "CINF",
    "Juniper Networks": "JNPR", "Western Digital": "WDC", "Loews Corporation": "L",
    "Jack Henry & Associates": "JKHY", "DENTSPLY SIRONA": "XRAY", "Snap-on": "SNA",
    "AES Corporation": "AES", "Sealed Air": "SEE", "PPL Corporation": "PPL",
    "Huntington Bancshares": "HBAN", "Ralph Lauren": "RL", "Regency Centers": "REG",
    "Boston Properties": "BXP", "American Airlines Group": "AAL", "NRG Energy": "NRG",
    "Pinnacle West Capital": "PNW", "Devon Energy": "DVN", "Healthpeak Properties": "PEAK",
    "Viatris": "VTRS", "Campbell Soup": "CPB", "Whirlpool Corporation": "WHR", "Kohl's": "KSS",
    "Hasbro": "HAS", "Newell Brands": "NWL", "Etsy": "ETSY", "Quanta Services": "PWR",
    "ABIOMED": "ABMD", "Trimble": "TRMB", "Qorvo": "QRVO", "Gartner": "IT", "EPAM Systems": "EPAM",
    "Rollins": "ROL", "Incyte": "INCY", "Paycom Software": "PAYC", "FactSet Research Systems": "FDS",
    "Assurant": "AIZ", "ServiceNow": "NOW", "Workday": "WDAY", "Splunk": "SPLK", "Roku": "ROKU",
    "Square": "SQ", "Twilio": "TWLO", "Zendesk": "ZEN", "Zscaler": "ZS", "Okta": "OKTA",
    "CrowdStrike Holdings": "CRWD", "DocuSign": "DOCU", "Zoom Video Communications": "ZM",
    "Datadog": "DDOG", "Cloudflare": "NET", "Slack Technologies": "WORK", "Snowflake": "SNOW",
    "RingCentral": "RNG", "Chewy": "CHWY", "Pinterest": "PINS", "Spotify Technology": "SPOT",
    "Shopify": "SHOP", "Atlassian": "TEAM", "Unity Software": "U", "Palantir Technologies": "PLTR",
    "DoorDash": "DASH", "Airbnb": "ABNB", "Coupa Software": "COUP", "ZoomInfo Technologies": "ZI",
    "Bill.com Holdings": "BILL", "Fastly": "FSLY", "MongoDB": "MDB", "Veeva Systems": "VEEV",

    "HubSpot": "HUBS", "Elastic": "ESTC", "Alteryx": "AYX", "Avalara": "AVLR", "Five9": "FIVN",
    "Ceridian HCM Holding": "CDAY", "Dropbox": "DBX", "Guidewire Software": "GWRE",
    "New Relic": "NEWR", "Robinhood Markets": "HOOD", "Coinbase Global": "COIN", "UiPath": "PATH",
    "Toast": "TOST", "Roblox Corporation": "RBLX", "AppLovin": "APP", "Marqeta": "MQ",
    "Affirm Holdings": "AFRM", "ContextLogic": "WISH", "Oscar Health": "OSCR", "Coupang": "CPNG",
    "Didi Global": "DIDI", "Playtika Holding": "PLTK", "Bumble": "BMBL", "ThredUp": "TDUP",
    "Blend Labs": "BLND", "Compass": "COMP", "ACV Auctions": "ACVA", "Coursera": "COUR",
    "Certara": "CERT", "C3.ai": "AI", "Qualtrics International": "XM", "Procore Technologies": "PCOR",
    "Samsara": "IOT", "Freshworks": "FRSH", "ForgeRock": "FORG", "Amplitude": "AMPL",
    "Warby Parker": "WRBY", "Rent the Runway": "RENT", "Allbirds": "BIRD", "Sweetgreen": "SG",
    "Duolingo": "DUOL", "Braze": "BRZE", "HashiCorp": "HCP", "Expensify": "EXFY", "Udemy": "UDMY",
    "Gitlab": "GTLB", "Remitly Global": "RELY", "Thoughtworks Holding": "TWKS", "Couchbase": "BASE",
    "WalkMe": "WKME", "Integral Ad Science Holding": "IAS", "Sprinklr": "CXM",
    "Frontier Group Holdings": "ULCC", "Compass Pathways": "CMPS", "Recursion Pharmaceuticals": "RXRX",
    "Zymergen": "ZY", "Ginkgo Bioworks Holdings": "DNA", "23andMe Holding": "ME",
    "Beam Therapeutics": "BEAM", "Sana Biotechnology": "SANA", "Lyell Immunopharma": "LYEL",
    "Seer": "SEER", "Berkeley Lights": "BLI", "Nuvei Corporation": "NVEI", "Global-e Online": "GLBE",
    "Payoneer Global": "PAYO", "Flywire": "FLYW", "Alkami Technology": "ALKT", "Squarespace": "SQSP",
    "DigitalOcean Holdings": "DOCN", "Informatica": "INFA", "Confluent": "CFLT"
}




end_date = datetime(2024, 8, 5)
start_date = datetime(2024, 1, 1)
current_date = start_date

print("Script started")
print(f"Start date: {start_date}")
print(f"End date: {end_date}")
print(f"Number of search terms: {len(search_terms)}")
print("First few search terms:")
for term in search_terms[:5]:
    print(term)

try:
    while current_date <= end_date:
        next_month = current_date + timedelta(days=30)
        if next_month > end_date:
            next_month = end_date

        start_date_str = current_date.strftime('%m/%d/%Y').lstrip('0').replace('/0', '/')
        end_date_str = next_month.strftime('%m/%d/%Y').lstrip('0').replace('/0', '/')

        for search_term in search_terms:
            print(f"Searching for '{search_term}' from {start_date_str} to {end_date_str}")

            proxy_extension_dir = f"proxy_extensions/{uuid.uuid4()}"
            os.makedirs(proxy_extension_dir, exist_ok=True)
            try:
                articles = google_news_search(search_term, start_date_str, end_date_str, proxy_extension_dir)
            finally:
                shutil.rmtree(proxy_extension_dir, ignore_errors=True)

            print(f"Scraped {len(articles)} articles for the search term: {search_term}")

            for article in articles:
                print(f"Processing article: {article['title']}")
                print(f"Date string: {article['date']}")
                
                try:
                    Datetime = datetime.strptime(article['date'], "%b %d, %Y")
                    Date = Datetime.date()
                    print(f"Successfully parsed date: {Datetime}")
                except ValueError:
                    ago_date = parse_ago_format(article['date'])
                    if ago_date:
                        Datetime = ago_date
                        Date = ago_date.date()
                        print(f"Parsed 'ago' format date: {Datetime}")
                    else:
                        print(f"Error: Unable to parse date '{article['date']}' for article: {article['title']}")
                        print(f"Full article data: {article}")
                        continue

                category = "company_specific_artificial_intelligence"

                symbol = None
                for company_name in company_names:
                    if company_name in search_term:
                        symbol = symbol_mapping.get(company_name)
                        break

                article_data = {
                    'url': article['url'],
                    'datetime': Datetime,
                    'summary': '',
                    'full_text': article['body'],
                    'title': article['title'],
                    'body': article['body'],
                    'date': Date,
                    'search_term': search_term,
                    'symbol': symbol,
                    'category': category
                }

                try:
                    create_table_query(article_data, db_config)
                except Exception as e:
                    print(f"Error inserting article into database: {e}")

            time.sleep(2)

        current_date = next_month

except Exception as e:
    print(f"An unexpected error occurred: {str(e)}")
    raise

print("Script completed")
