import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 提取文本函數
def extract_text(driver, xpath):
    element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    return element.text.strip().replace('\n', '<br>').replace('"', r'\"')

# 提取 trace 數據並寫入 trace.txt
def extract_trace_data(driver, trace_file_path):
    # 清空文件內容
    with open(trace_file_path, 'w', encoding='utf-8') as file:
        file.write('')  # 清空文件
    
    try:
        # 爬取 Bonus Ability 信息
        bonus_ability = extract_text(driver, "//span[text()='Bonus Ability']/ancestor::div[contains(@class, 'flex flex-col')]")
        print(f"Extracted Bonus Ability: {bonus_ability}")

        # 查找 trace 1, 2, 3 的內容
        trace_1_name = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='1.']/following-sibling::div[@class='text-sm font-normal']")
        trace_1_desc = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='1.']/following-sibling::div[@class='text-sm font-normal']/following-sibling::div[@class='text-sm font-normal']")
        
        trace_2_name = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='2.']/following-sibling::div[@class='text-sm font-normal']")
        trace_2_desc = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='2.']/following-sibling::div[@class='text-sm font-normal']/following-sibling::div[@class='text-sm font-normal']")
        
        trace_3_name = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='3.']/following-sibling::div[@class='text-sm font-normal']")
        trace_3_desc = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='3.']/following-sibling::div[@class='text-sm font-normal']/following-sibling::div[@class='text-sm font-normal']")
        
        # 確認 1 和 3 是 A Name 還是 C Name
        ascension_1 = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='1.']/ancestor::div[contains(@class, 'flex')]/following-sibling::div[@class='px-3 py-2 mx-auto text-xs font-normal text-center text-red-300 rounded-full bg-red-950']")
        ascension_3 = extract_text(driver, "//div[@class='inline-block text-indigo-500' and text()='3.']/ancestor::div[contains(@class, 'flex')]/following-sibling::div[@class='px-3 py-2 mx-auto text-xs font-normal text-center text-red-300 rounded-full bg-red-950']")

        # 確定 A Name 與 C Name 的順序
        if "Ascension 2" in ascension_1:
            a_name = trace_1_name
            a_desc = trace_1_desc
            c_name = trace_3_name
            c_desc = trace_3_desc
        else:
            a_name = trace_3_name
            a_desc = trace_3_desc
            c_name = trace_1_name
            c_desc = trace_1_desc

        # 寫入文件
        with open(trace_file_path, 'w', encoding='utf-8') as file:
            file.write(f"a_name={a_name}\n")
            file.write(f"a_desc={a_desc}\n")
            file.write(f"b_name={trace_2_name}\n")
            file.write(f"b_desc={trace_2_desc}\n")
            file.write(f"c_name={c_name}\n")
            file.write(f"c_desc={c_desc}\n")
        
        print(f"Trace data successfully written to {trace_file_path}")

    except Exception as e:
        print(f"Error extracting trace data: {e}")

def main():
    try:
        # 使用 Chrome WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 可選，無頭模式
        chrome_options.add_argument("--log-level=3")  # 禁用日誌
        chrome_options.add_argument("--disable-gpu")  # 禁用 GPU
        chrome_options.add_argument("--lang=en")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        # 進入網址
        url = 'https://example.com/trace_page'  # 替換為實際的頁面 URL
        driver.get(url)

        # 執行 trace 數據提取
        extract_trace_data(driver, 'trace.txt')

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
