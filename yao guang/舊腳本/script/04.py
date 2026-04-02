import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def extract_text(driver, xpath):
    element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    return element.text.strip().replace('\n', '<br>')

def extract_eidolons_data(driver):
    eidolons_data = {}
    eidolons_section = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Eidolons')]/ancestor::div[contains(@class, 'flex flex-col')]"))
    )
    eidolon_entries = eidolons_section.find_elements(By.XPATH, ".//div[@class='flex flex-col']")

    for i, eidolon in enumerate(eidolon_entries, start=1):
        name_element = eidolon.find_element(By.XPATH, ".//div[contains(@class, 'text-lg')]")
        desc_element = eidolon.find_element(By.XPATH, ".//div[contains(@class, 'text-sm font-normal')]")
        eidolon_name = name_element.text.strip().split(' ', 1)[1]
        eidolon_desc = desc_element.text.strip().replace('\n', '<br>').replace('"', r'\"')

        eidolons_data[f'Eidolons{i}name'] = eidolon_name
        eidolons_data[f'Eidolons{i}desc'] = eidolon_desc
        print(f"Eidolons {i} extracted: {eidolon_name} - {eidolon_desc}")

    return eidolons_data

def extract_stat_data(driver, stat_data):
    stat_data['normalatkname'] = extract_text(driver, "//div[contains(text(), 'Basic ATK')]/following-sibling::div[@class='pb-1 text-base']")
    stat_data['normalatk2name'] = ""  # Assuming there is no second normal attack name
    stat_data['skillname'] = extract_text(driver, "//div[contains(text(), 'Skill')]/following-sibling::div[@class='pb-1 text-base']")
    stat_data['skilltitle'] = extract_text(driver, "//div[contains(text(), 'Skill')]/following-sibling::div[@class='pb-1 text-base text-indigo-500']")
    stat_data['ultimatename'] = extract_text(driver, "//div[contains(text(), 'Ultimate')]/following-sibling::div[@class='pb-1 text-base']")
    stat_data['ultimatetitle'] = extract_text(driver, "//div[contains(text(), 'Ultimate')]/following-sibling::div[@class='pb-1 text-base text-indigo-500']")
    stat_data['talentname'] = extract_text(driver, "//div[contains(text(), 'Talent')]/following-sibling::div[@class='pb-1 text-base']")
    stat_data['talenttitle'] = extract_text(driver, "//div[contains(text(), 'Talent')]/following-sibling::div[@class='pb-1 text-base text-indigo-500']")
    stat_data['Techniquename'] = extract_text(driver, "//div[contains(text(), 'Technique')]/following-sibling::div[@class='pb-1 text-base']")
    stat_data['Techniquetitle'] = extract_text(driver, "//div[contains(text(), 'Technique')]/following-sibling::div[@class='pb-1 text-base text-indigo-500']")
    stat_data['Techniquedesc'] = extract_text(driver, "//div[contains(text(), 'Technique')]/following-sibling::div[@class='text-sm font-normal']").replace('"', r'\"')

    print(stat_data)

def extract_overview_and_max_energy(driver):
    data = {}
    # Extract overview1 with updated class
    overview_element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'flex flex-col self-end py-2 text-xs font-normal')]"))
    )
    data['overview1'] = overview_element.text.strip().replace('\n', '<br>')
    print(f"Extracted overview1: {data['overview1']}")

    # Extract max energy
    max_energy_element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Max Energy')]/following-sibling::div"))
    )
    data['6'] = max_energy_element.text.strip()
    print(f"Extracted Max Energy: {data['6']}")

    return data

def extract_section_data(driver, section_xpath, stat_key):
    section_element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, section_xpath))
    )
    text_element = section_element.text.strip().replace('\n', '<br>')
    print(f"Extracted {stat_key}: {text_element}")
    return text_element  # Only return the value

def extract_trace_data(trace_file_path):
    trace_data = {}
    try:
        with open(trace_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

            # Clean up the lines by removing "1.", "2.", or "3."
            def clean_line(line):
                return line.replace("1. ", "").replace("2. ", "").replace("3. ", "").strip()

            # Assign the cleaned values
            trace_data['Aname'] = clean_line(lines[6].strip())  # Assuming 3rd trace's name
            trace_data['Adesc'] = lines[7].strip()  # Assuming 3rd trace's description
            trace_data['Bname'] = clean_line(lines[4].strip())  # Assuming 2nd trace's name
            trace_data['Bdesc'] = lines[5].strip()  # Assuming 2nd trace's description
            trace_data['Cname'] = clean_line(lines[2].strip())  # Assuming 1st trace's name
            trace_data['Cdesc'] = lines[3].strip()  # Assuming 1st trace's description

        return trace_data

    except Exception as e:
        print(f"Error processing trace data: {e}")
        return trace_data


def main():
    try:
        with open('link.txt', 'r') as file:
            urls = file.readlines()

        if not urls:
            print("No URLs found in link.txt.")
            return

        section_xpaths = {
            '1': "//div[contains(text(), 'HP')]/following-sibling::div",
            '2': "//div[contains(text(), 'ATK')]/following-sibling::div",
            '3': "//div[contains(text(), 'DEF')]/following-sibling::div",
            '4': "//div[contains(text(), 'Speed')]/following-sibling::div",
            '5': "//div[contains(text(), 'Taunt')]/following-sibling::div",
            '6': "//div[contains(text(), 'Max Energy')]/following-sibling::div",
            'overview1': "//div[contains(@class, 'flex flex-col self-end py-2 text-xs font-normal')]"
        }

        stat_raw_template = {
            '1': "",
            '2': "",
            '3': "",
            '4': "",
            '5': "",
            '6': "",
            'overview1': "",
            'Eidolons1name': "",
            'Eidolons1desc': "",
            'Eidolons2name': "",
            'Eidolons2desc': "",
            'Eidolons3name': "",
            'Eidolons3desc': "",
            'Eidolons4name': "",
            'Eidolons4desc': "",
            'Eidolons5name': "",
            'Eidolons5desc': "",
            'Eidolons6name': "",
            'Eidolons6desc': "",
            'normalatkname': "",
            'normalatk2name': "",
            'skillname': "",
            'skilltitle': "",
            'ultimatename': "",
            'ultimatetitle': "",
            'talentname': "",
            'talenttitle': "",
            'Techniquename': "",
            'Techniquetitle': "",
            'Techniquedesc': "",
            'Aname': "",
            'Adesc': "",
            'Bname': "",
            'Bdesc': "",
            'Cname': "",
            'Cdesc': ""
        }

        for url in urls:
            url = url.strip()
            if url:
                print(f"Processing URL: {url}")
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--log-level=3")
                
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

                try:
                    driver.get(url)

                    extracted_data = {}
                    for key, xpath in section_xpaths.items():
                        extracted_data[key] = extract_section_data(driver, xpath, key)

                    eidolons_data = extract_eidolons_data(driver)
                    extracted_data.update(eidolons_data)

                    extract_stat_data(driver, extracted_data)  # Combine stat data extraction from 05.py

                    overview_and_energy = extract_overview_and_max_energy(driver)
                    extracted_data.update(overview_and_energy)

                    # Extract trace data from the skill_data/trace.txt
                    trace_data = extract_trace_data(os.path.join('skill_data', 'trace.txt'))
                    extracted_data.update(trace_data)

                    mapped_data = stat_raw_template.copy()
                    mapped_data.update(extracted_data)

                    output_file = 'character_stat.txt'
                    with open(output_file, 'w', encoding='utf-8') as file:
                        for key, value in mapped_data.items():
                            file.write(f"'{key}': \"{value}\",\n")
                    print(f"Data successfully written to {output_file}")

                finally:
                    driver.quit()

    except FileNotFoundError:
        print("Error: link.txt file not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
