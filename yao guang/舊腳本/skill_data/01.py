import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests
from requests.exceptions import RequestException
import time
from selenium.common.exceptions import TimeoutException

def get_script_directory():
    """獲取腳本所在的目錄路徑"""
    return os.path.dirname(os.path.abspath(__file__))

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

def extract_section_data(driver, section_name, output_file):
    try:
        # 首先找到 SKILLS 部分
        skills_section_xpath = "//div[contains(@class, 'flex flex-col self-start')]//span[contains(text(), 'SKILLS')]/ancestor::div[contains(@class, 'flex flex-col self-start')]"
        
        # 等待 SKILLS 部分出現
        skills_section = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, skills_section_xpath))
        )
        print("找到 SKILLS 部分")

        # 在 SKILLS 部分中尋找指定的技能部分
        section_xpath = f".//div[contains(@class, 'py-2')]//div[contains(@class, 'text-lg') and contains(text(), '{section_name}')]/ancestor::div[contains(@class, 'py-2')]"
        
        # 等待具體技能部分出現
        section_element = WebDriverWait(skills_section, 30).until(
            EC.presence_of_element_located((By.XPATH, section_xpath))
        )
        print(f"找到 {section_name} 部分")

        # 等待滑塊元素出現
        slider_element = WebDriverWait(section_element, 10).until(
            EC.presence_of_element_located((By.XPATH, ".//input[@type='range']"))
        )
        
        # 獲取最大等級
        max_level = int(slider_element.get_attribute('max'))
        print(f"{section_name} 的最大等級: {max_level}")

        changes = []
        # 等待文本元素出現
        initial_text_element = WebDriverWait(section_element, 10).until(
            EC.presence_of_element_located((By.XPATH, ".//div[contains(@class, 'text-sm font-normal')]"))
        )
        
        for level in range(1, max_level + 1):
            try:
                # 使用 JavaScript 設置滑塊值
                driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    slider_element, level
                )
                
                # 等待文本更新
                time.sleep(0.5)  # 給頁面一些時間來更新
                
                # 獲取更新後的文本
            updated_text = initial_text_element.text.strip()
                if updated_text:  # 確保文本不為空
            changes.append(f"Level {level}: {updated_text}")
            print(f"{section_name} - Level {level}: {updated_text}")
                else:
                    print(f"警告：Level {level} 的文本為空")
                    
            except Exception as e:
                print(f"處理 Level {level} 時發生錯誤: {e}")
                continue

        if changes:  # 只有在有數據時才寫入文件
            with open(output_file, "w", encoding='utf-8') as file:
            for change in changes:
                file.write(change + "\n")
            print(f"數據已成功保存到 {output_file}")
        else:
            print(f"警告：{section_name} 沒有找到任何數據")

    except TimeoutException:
        print(f"超時：無法找到 {section_name} 部分")
    except Exception as e:
        print(f"處理 {section_name} 時發生錯誤: {e}")

def extract_and_combine_limited_section_data(driver, output_file):
    sections = ["Basic ATK", "Skill", "Ultimate", "Talent", "Technique"]
    combined_content = ""

    try:
        # 首先找到 SKILLS 部分
        skills_section_xpath = "//div[contains(@class, 'flex flex-col self-start')]//span[contains(text(), 'SKILLS')]/ancestor::div[contains(@class, 'flex flex-col self-start')]"
        
        # 等待 SKILLS 部分出現
        skills_section = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, skills_section_xpath))
        )
        print("找到 SKILLS 部分")

        for section_name in sections:
            try:
                # 在 SKILLS 部分中尋找指定的技能部分
                section_xpath = f".//div[contains(@class, 'py-2')]//div[contains(@class, 'text-lg') and contains(text(), '{section_name}')]/ancestor::div[contains(@class, 'py-2')]"
                
                # 等待具體技能部分出現
                section_element = WebDriverWait(skills_section, 30).until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
                print(f"找到 {section_name} 部分")

                # 等待內容元素出現
                content_elements = WebDriverWait(section_element, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, ".//div"))
                )
                
            content = []
            for element in content_elements:
                text = element.text.strip()
                if text and text not in content:
                    content.append(text)
                if "Weakness Break" in text:
                    break

                if content:
            combined_content += f"{section_name}\n" + "\n".join(content) + "\n\n"
                else:
                    print(f"警告：{section_name} 沒有找到任何內容")

            except TimeoutException:
                print(f"超時：無法找到 {section_name} 部分")
            except Exception as e:
                print(f"處理 {section_name} 時發生錯誤: {e}")
                continue

        if combined_content:
        with open(output_file, "w", encoding='utf-8') as file:
            file.write(combined_content.strip())
            print(f"技能數據已成功保存到 {output_file}")
        else:
            print("警告：沒有找到任何技能數據")

    except Exception as e:
        print(f"處理技能數據時發生錯誤: {e}")

def extract_bonus_ability_data(driver, output_file):
    try:
        # 使用更精確的 XPath 定位
        bonus_ability_xpath = "//span[contains(text(), 'BONUS ABILITY')]/ancestor::div[contains(@class, 'flex flex-col p-4 m-4')]"
        bonus_ability_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, bonus_ability_xpath))
        )

        content_text = bonus_ability_element.text.strip()
        if content_text:
        with open(output_file, "a", encoding="utf-8") as file:
            file.write(content_text + "\n\n")
            print(f"額外能力數據已保存到 {output_file}")
        else:
            print("警告：沒有找到額外能力數據")

    except TimeoutException:
        print("超時：無法找到額外能力部分")
    except Exception as e:
        print(f"提取額外能力內容時發生錯誤: {e}")

def main():
    try:
        # 獲取腳本所在目錄
        script_dir = get_script_directory()
        
        # 構建 link.txt 的完整路徑
        link_file_path = os.path.join(script_dir, 'link.txt')
        
        # 檢查文件是否存在
        if not os.path.exists(link_file_path):
            print(f"錯誤：找不到 link.txt 文件。請確保文件位於：{link_file_path}")
            return

        # 讀取 URL
        with open(link_file_path, 'r', encoding='utf-8') as file:
            urls = [line.strip() for line in file.readlines() if line.strip()]

        if not urls:
            print("警告：link.txt 文件中沒有找到有效的 URL。")
            return

        # 創建輸出目錄（在腳本所在目錄下）
        output_dir = os.path.join(script_dir, 'skill_data')
        os.makedirs(output_dir, exist_ok=True)

        for url in urls:
            # 處理 URL 格式
            if not url.startswith('http'):
                url = f'https://hsr20.hakush.in/char/{url}/'
            
            print(f"正在處理 URL: {url}")
            
            # 檢查網站可用性
            if not check_website_availability(url):
                print(f"無法訪問網站 {url}，跳過處理")
                continue

            # 設置 Chrome 選項
                chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
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
                    driver.set_page_load_timeout(30)

                try:
                    driver.get(url)

                        # 等待頁面加載完成
                        WebDriverWait(driver, 20).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )

                        # 從 URL 中提取角色 ID 作為文件名前綴
                        char_id = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                        
                        # 使用角色 ID 作為文件名前綴
                        extract_section_data(driver, "Basic ATK", os.path.join(output_dir, f"{char_id}_basic_atk.txt"))
                        extract_section_data(driver, "Skill", os.path.join(output_dir, f"{char_id}_skill.txt"))
                        extract_section_data(driver, "Ultimate", os.path.join(output_dir, f"{char_id}_ultimate.txt"))
                        extract_section_data(driver, "Talent", os.path.join(output_dir, f"{char_id}_talent.txt"))
                        extract_and_combine_limited_section_data(driver, os.path.join(output_dir, f"{char_id}_skill_raw.txt"))
                        extract_bonus_ability_data(driver, os.path.join(output_dir, f"{char_id}_trace.txt"))

                        print(f"成功處理 URL: {url}")
                        break  # 如果成功執行，跳出重試循環

                    except Exception as e:
                        print(f"處理數據時發生錯誤: {e}")
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"正在進行第 {retry_count + 1} 次重試...")
                            time.sleep(2)
                        else:
                            print("達到最大重試次數，跳過此 URL")
                finally:
                    driver.quit()

                except Exception as e:
                    print(f"WebDriver 初始化錯誤: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"正在進行第 {retry_count + 1} 次重試...")
                        time.sleep(2)
                    else:
                        print("達到最大重試次數，跳過此 URL")

    except Exception as e:
        print(f"發生未預期的錯誤: {e}")

if __name__ == "__main__":
    main()

