import os
import csv
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
import requests
from requests.exceptions import RequestException

def ensure_directory_exists(file_path):
    """確保文件所在的目錄存在"""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def check_if_exists(version, csv_path):
    """檢查版本是否已存在於CSV文件的A列中"""
    if not os.path.exists(csv_path):
        return False
    try:
        with open(csv_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                if row and row[0] == version:
                    return True
    except Exception as e:
        print(f"讀取CSV文件時發生錯誤: {e}")
    return False

def check_website_availability(url, max_retries=3):
    """檢查網站是否可訪問"""
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return True
        except RequestException:
            if i < max_retries - 1:
                print(f"網站訪問失敗，正在進行第 {i+2} 次嘗試...")
                time.sleep(2)
            continue
    return False

def extract_update_log(driver, csv_writer, csv_path):
    """提取更新日誌版本並決定是否繼續"""
    url = "https://hsr20.hakush.in/"
    
    # 首先檢查網站是否可訪問
    if not check_website_availability(url):
        print("無法訪問目標網站，請檢查網絡連接或網站是否可用")
        return
    
    try:
        # 設置頁面加載超時
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        # 等待頁面加載完成
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # 獲取版本信息
        version_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(@class, 'font-light ml-8')]"))
        )
        version_text = version_element.text.strip().replace("updated!", "").strip()
        print(f"找到版本: {version_text}")
        
        # 檢查此版本是否存在於CSV中
        if check_if_exists(version_text, csv_path):
            print(f"版本 {version_text} 已存在。跳過後續步驟。")
            return
        
        # 如果版本不存在，寫入A列（更新日誌）
        csv_writer.writerow([version_text, '', '', '', '', '', ''])  # B到G列留空作為佔位符
        
        # 繼續從div元素提取數據
        extract_data_from_divs(driver, csv_writer)
        
    except TimeoutException:
        print("頁面加載超時，請檢查網絡連接")
    except WebDriverException as e:
        print(f"WebDriver錯誤: {str(e)}")
    except Exception as e:
        print(f"提取更新日誌時發生錯誤: {str(e)}")

def extract_data_from_divs(driver, csv_writer):
    """Extract information from the DIV elements on the page."""
    try:
        # Locate all relevant div elements with character info
        div_blocks = driver.find_elements(By.XPATH, "//div[contains(@class, 'flex justify-center p-3 text-slate-950 grid')]")
        
        for index, block in enumerate(div_blocks):
            # Determine link type based on index
            if index == 0:
                link_type = "character"
            elif index == 1:
                link_type = "lightcone"
            elif index == 2:
                link_type = "relics"
            elif index == 3:
                continue  # Skip the monster block
            else:
                link_type = "unknown"
            
            if link_type == "relics":
                # Extract relics information
                relic_elements = block.find_elements(By.XPATH, ".//div[contains(@class, 'grid grid-cols-6 p-2 text-slate-100 py-4')]")
                for relic in relic_elements:
                    # Extract relic link
                    relic_link = relic.find_element(By.XPATH, ".//a[contains(@class, 'col-span-2')]").get_attribute("href")
                    # Extract image link
                    image_link = relic.find_element(By.XPATH, ".//img[contains(@class, 'avatar-icon-front')]").get_attribute("src")
                    # Extract relic name
                    relic_name = relic.find_element(By.XPATH, ".//a[contains(@class, 'text-lg pb-1 font-bold flex')]").text
                    # Extract relic description
                    desc_elements = relic.find_elements(By.XPATH, ".//div[contains(@class, 'text-sm font-normal')]")
                    relic_desc = " ".join([desc.text for desc in desc_elements if "2-Pc:" in desc.text or "4-Pc:" in desc.text])
                    # Write all extracted information to CSV
                    csv_writer.writerow([relic_link, image_link, link_type, relic_name, "Unknown", "Unknown", relic_desc])
            else:
                div_elements = block.find_elements(By.XPATH, ".//a[contains(@class, 'avatar-icon-front-a')] | .//a[contains(@class, 'avatar-icon-front')]")
                
                for div in div_elements:
                    # Extract link
                    character_link = div.get_attribute("href")
                    print(f"Processing character link: {character_link}")
                    
                    # Extract image link
                    image_element = div.find_element(By.XPATH, ".//img[contains(@class, 'avatar-icon-front')]")
                    image_link = image_element.get_attribute("src")
                    
                    # Extract character name (in English)
                    character_name = div.find_element(By.XPATH, ".//div[contains(@class, 'p-2 text-center')] | .//div[contains(@class, 'text-center')]").text
                    
                    # Extract character element from image link if available
                    character_element = "Unknown"
                    try:
                        # More flexible search for element image
                        element_img = div.find_element(By.XPATH, ".//img[contains(@src, 'element')]")
                        element_src = element_img.get_attribute("src")
                        character_element = get_element_type(element_src)
                    except Exception as e:
                        print(f"Element icon not found for link {character_link}, setting element as Unknown")
                        character_element = "Unknown"
                    
                    # Extract path
                    try:
                        path_img = div.find_element(By.XPATH, ".//img[contains(@class, 'absolute h-6 w-6 top-0 right-0')]")
                        path_src = path_img.get_attribute("src")
                        path_type = get_path_type(path_src)
                    except Exception as e:
                        print(f"Path icon not found for link {character_link}, setting path as Unknown")
                        path_type = "Unknown"
                    
                    # Write all extracted information to CSV
                    csv_writer.writerow([character_link, image_link, link_type, character_name, character_element, path_type, ""])

    except Exception as e:
        print(f"An error occurred while extracting data from div elements: {e}")

def get_path_type(src):
    """Determine the path type based on the image source."""
    path_mapping = {
        "knight": "The Preservation",
        "mage": "The Erudition",
        "priest": "The Abundance",
        "rogue": "The Hunt",
        "shaman": "The Harmony",
        "warlock": "The Nihility",
        "warrior": "The Destruction"
    }
    for key, value in path_mapping.items():
        if key in src:
            return value
    return "Unknown"

def get_element_type(src):
    """Determine the element type based on the image source."""
    element_mapping = {
        "fire": "Fire",
        "ice": "Ice",
        "imaginary": "Imaginary",
        "physical": "Physical",
        "quantum": "Quantum",
        "thunder": "Lightning",
        "wind": "Wind"
    }
    for key, value in element_mapping.items():
        if key in src:
            return value
    return "Unknown"

def main():
    try:
        # CSV文件路徑
        csv_path = "UPDATE_LOG.CSV"
        
        # 確保目錄存在
        ensure_directory_exists(csv_path)
        
        # 設置Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--lang=en")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # 設置重試次數
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                
                try:
                    with open(csv_path, "a", newline='', encoding='utf-8') as csv_file:
                        csv_writer = csv.writer(csv_file)
                        
                        if not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0:
                            csv_writer.writerow(["LINK", "LINK IMG", "LINK TYPE", "NAME", "ELEMENT", "PATH", "DESC"])
                        
                        extract_update_log(driver, csv_writer, csv_path)
                        break  # 如果成功執行，跳出重試循環
                        
                except IOError as e:
                    print(f"文件操作錯誤: {e}")
                    break
                except Exception as e:
                    print(f"處理數據時發生錯誤: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"正在進行第 {retry_count + 1} 次重試...")
                        time.sleep(2)
                    else:
                        print("達到最大重試次數，程序終止")
                finally:
                    driver.quit()
                    
            except Exception as e:
                print(f"WebDriver初始化錯誤: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"正在進行第 {retry_count + 1} 次重試...")
                    time.sleep(2)
                else:
                    print("達到最大重試次數，程序終止")
    
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")

if __name__ == "__main__":
    main()
