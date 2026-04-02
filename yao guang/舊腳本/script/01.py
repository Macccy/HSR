import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def extract_section_data(driver, section_name, output_file):
    try:
        section_xpath = f"//div[contains(@class, 'py-2') and div[text()='{section_name}']]"
        section_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, section_xpath))
        )
        print(f"{section_name} section found.")

        slider_element = section_element.find_element(By.XPATH, ".//input[@type='range']")
        max_level = int(slider_element.get_attribute('max'))
        print(f"Max slider level for {section_name}: {max_level}")

        changes = []
        initial_text_element = section_element.find_element(By.XPATH, ".//div[contains(@class, 'text-sm font-normal')]")
        
        for level in range(1, max_level + 1):
            driver.execute_script(f"arguments[0].value = {level}; arguments[0].dispatchEvent(new Event('input'));", slider_element)
            updated_text = initial_text_element.text.strip()
            changes.append(f"Level {level}: {updated_text}")
            print(f"{section_name} - Level {level}: {updated_text}")

        with open(output_file, "w") as file:
            for change in changes:
                file.write(change + "\n")
        print(f"Data successfully saved to {output_file}")

    except Exception as e:
        print(f"An error occurred while processing {section_name}: {e}")

def extract_and_combine_limited_section_data(driver, output_file):
    sections = ["Basic ATK", "Skill", "Ultimate", "Talent", "Technique"]
    combined_content = ""

    try:
        for section_name in sections:
            section_xpath = f"//div[contains(@class, 'py-2') and div[text()='{section_name}']]"
            section_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
            print(f"{section_name} section found.")

            # Start extracting the text
            content_elements = section_element.find_elements(By.XPATH, ".//div")
            content = []
            for element in content_elements:
                text = element.text.strip()
                # Avoid duplicates by checking if the content is already in the list
                if text and text not in content:
                    content.append(text)
                # Stop if "Weakness Break" is encountered
                if "Weakness Break" in text:
                    break

            combined_content += f"{section_name}\n" + "\n".join(content) + "\n\n"

        with open(output_file, "w", encoding='utf-8') as file:
            file.write(combined_content.strip())
        print(f"Combined skill data successfully saved to {output_file}")

    except Exception as e:
        print(f"An error occurred while processing the combined skill data: {e}")

def extract_bonus_ability_data(driver, output_file):
    try:
        bonus_ability_xpath = "//span[contains(text(), 'BONUS ABILITY')]/ancestor::div[contains(@class, 'flex flex-col p-4 m-4')]"
        bonus_ability_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, bonus_ability_xpath))
        )

        content_text = bonus_ability_element.text.strip()

        with open(output_file, "a", encoding="utf-8") as file:
            file.write(content_text + "\n\n")
        print(f"Bonus Ability data saved to {output_file}")

    except Exception as e:
        print(f"An error occurred while extracting BONUS ABILITY content: {e}")

def main():
    try:
        with open('link.txt', 'r') as file:
            urls = file.readlines()

        if not urls:
            print("No URLs found in link.txt.")
            return

        output_dir = 'skill_data'
        os.makedirs(output_dir, exist_ok=True)

        for url in urls:
            url = url.strip()
            if url:
                print(f"Processing URL: {url}")
                chrome_options = Options()
                chrome_options.add_argument("--headless")  # Optional: run in headless mode
                chrome_options.add_argument("--log-level=3")  # Disable logs
                chrome_options.add_argument("--disable-logging")  # Disable logging
                chrome_options.add_argument("--disable-gpu")  # Disable GPU for headless mode
                chrome_options.add_argument("--disable-extensions")  # Disable extensions
                chrome_options.add_argument("--disable-images")  # Disable images for faster loading
                chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # Disable image rendering
                chrome_options.add_argument("--lang=en")

                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

                try:
                    driver.get(url)

                    extract_section_data(driver, "Basic ATK", os.path.join(output_dir, "basic_atk.txt"))
                    extract_section_data(driver, "Skill", os.path.join(output_dir, "skill.txt"))
                    extract_section_data(driver, "Ultimate", os.path.join(output_dir, "ultimate.txt"))
                    extract_section_data(driver, "Talent", os.path.join(output_dir, "talent.txt"))

                    # Combine the limited section data into a single file
                    extract_and_combine_limited_section_data(driver, os.path.join(output_dir, "skill_raw.txt"))
                    
                    extract_bonus_ability_data(driver, os.path.join(output_dir, "trace.txt"))

                finally:
                    driver.quit()

    except FileNotFoundError:
        print("Error: link.txt file not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

