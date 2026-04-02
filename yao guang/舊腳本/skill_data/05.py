import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def extract_matched_elements(driver, section_name, output_file):
    try:
        # Locate the section based on section name
        section_xpath = f"//div[contains(@class, 'py-2') and div[text()='{section_name}']]"
        section_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, section_xpath))
        )
        print(f"{section_name} section found.")

        # Find all elements that meet the 3 conditions
        matched_elements = section_element.find_elements(By.XPATH, ".//div[contains(@class, 'pb-1 text-base text-indigo-500')] | .//div[contains(@class, 'pb-1 text-base')] | .//div[contains(@class, 'text-sm font-normal')]")
        
        # Verify if all 3 elements exist in the section
        indigo_elements = section_element.find_elements(By.XPATH, ".//div[contains(@class, 'pb-1 text-base text-indigo-500')]")
        base_elements = section_element.find_elements(By.XPATH, ".//div[contains(@class, 'pb-1 text-base')]")
        normal_elements = section_element.find_elements(By.XPATH, ".//div[contains(@class, 'text-sm font-normal')]")

        if indigo_elements and base_elements and normal_elements:
            print(f"All conditions matched for {section_name}.")
            content = f"--- {section_name} ---\n"
            # Loop through all matched elements and extract the text
            for element in matched_elements:
                content += element.text.strip() + "\n"

            # Locate the div that contains "Energy Regeneration" or "Weakness Break" inside the grid container
            grid_container_xpath = "//div[contains(@class, 'grid grid-cols-1 gap-1 p-4')]"
            grid_containers = section_element.find_elements(By.XPATH, grid_container_xpath)

            energy_regeneration_value = None
            weakness_break_value = None

            # Search for Energy Regeneration and Weakness Break in the grid container for the specific section
            for container in grid_containers:
                container_text = container.text.strip()
                if "Energy Regeneration" in container_text:
                    energy_regeneration_value = container_text.split("Energy Regeneration")[-1].strip()
                if "Weakness Break" in container_text:
                    weakness_break_value = container_text.split("Weakness Break")[-1].strip()

            # Append Energy Regeneration and Weakness Break values if found
            if energy_regeneration_value:
                content += f"Energy Regeneration: {energy_regeneration_value}\n"
            if weakness_break_value:
                content += f"Weakness Break: {weakness_break_value}\n"

            # Print the content to the console
            print(f"Content for {section_name}:\n{content}")

            # Write the extracted content to the output file
            with open(output_file, "a", encoding="utf-8") as file:
                file.write(content + "\n")
                file.write(f"Found {len(matched_elements)} matching elements in {section_name}.\n\n")

        else:
            print(f"Not all conditions matched for {section_name}.")

    except Exception as e:
        print(f"An error occurred while processing {section_name}: {e}")

def main():
    try:
        with open('link.txt', 'r') as file:
            urls = file.readlines()

        if not urls:
            print("No URLs found in link.txt.")
            return

        # Create the 'skill_data' directory if it does not exist
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
                    # Load the webpage
                    driver.get(url)

                    # Extract sections with 3 matching div elements and display the content
                    extract_matched_elements(driver, "Basic ATK", os.path.join(output_dir, "matched_basic_atk.txt"))
                    extract_matched_elements(driver, "Skill", os.path.join(output_dir, "matched_skill.txt"))
                    extract_matched_elements(driver, "Ultimate", os.path.join(output_dir, "matched_ultimate.txt"))
                    extract_matched_elements(driver, "Talent", os.path.join(output_dir, "matched_talent.txt"))
                    
                finally:
                    driver.quit()

    except FileNotFoundError:
        print("Error: link.txt file not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
