import csv
import os
import re
from collections import defaultdict

def extract_percentages(file_path, levels):
    """Extract percentage values for each level from the given file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    percentages = defaultdict(list)
    level_pattern = re.compile(r'Level\s*(\d+):')

    current_level = 0

    for line in lines:
        match = level_pattern.search(line)
        if match:
            current_level = int(match.group(1)) - 1

        if 0 <= current_level < levels:
            percentage_matches = re.findall(r'(\d+(\.\d+)?)%', line)
            for percentage in percentage_matches:
                percentages[current_level].append(percentage[0] + "%")

    return percentages

def collect_all_percentages():
    """Collect all percentages from the four files."""
    all_data = []
    
    # Extract percentages from all relevant files
    basic_atk_percentages = extract_percentages(*files["Basic atk"])
    skill_percentages = extract_percentages(*files["Skill"])
    ultimate_percentages = extract_percentages(*files["Ultimate"])
    talent_percentages = extract_percentages(*files["Talent"])

    # Collect data for Basic_atk (9 elements)
    all_data.extend([basic_atk_percentages.get(level, []) for level in range(9)])
    
    # Collect data for Skill, Ultimate, and Talent (15 elements each)
    for i in range(15):
        all_data.append(skill_percentages.get(i, []))
    for i in range(15):
        all_data.append(ultimate_percentages.get(i, []))
    for i in range(15):
        all_data.append(talent_percentages.get(i, []))
    
    return all_data

# Define the filenames
skill_data_dir = 'skill_data'
files = {
    "Basic atk": (os.path.join(skill_data_dir, "Basic_atk.txt"), 9),
    "Skill": (os.path.join(skill_data_dir, "skill.txt"), 15),
    "Ultimate": (os.path.join(skill_data_dir, "ultimate.txt"), 15),
    "Talent": (os.path.join(skill_data_dir, "talent.txt"), 15)
}

# Collect all percentage data
all_percentages = collect_all_percentages()

# Output all collected data to a CSV file for review
csv_output_path = os.path.join(skill_data_dir, 'restructured_skill_data_v3.csv')
with open(csv_output_path, 'w', newline='', encoding='utf-8') as csvfile:
    csvwriter = csv.writer(csvfile)
    for row in all_percentages:
        csvwriter.writerow(row)

# Read the CSV file into a list of lists
data = []
with open(csv_output_path, 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    for row in reader:
        # Remove any empty strings or extra spaces that were added
        clean_row = [item.strip() for item in row if item.strip()]
        data.append(clean_row)

# Initialize the dictionary for final data
final_data_corrected = {}

# Function to determine available columns and assign to corresponding keys
def assign_data_to_keys(start_row, end_row, start_key_index):
    """Assigns data from a specified row range to the correct keys based on the column count."""
    key_index = start_key_index
    for col in range(len(data[start_row])):
        key_name = f'a{key_index}'
        final_data_corrected[key_name] = [f'"{item}"' for item in [row[col] for row in data[start_row:end_row]]]
        key_index += 1
    return key_index

# Assign data dynamically based on available columns
current_key_index = 1
current_key_index = assign_data_to_keys(0, 9, current_key_index)  # Basic atk (9 rows)
current_key_index = assign_data_to_keys(9, 24, current_key_index)  # Skill (15 rows)
current_key_index = assign_data_to_keys(24, 39, current_key_index)  # Ultimate (15 rows)
current_key_index = assign_data_to_keys(39, 54, current_key_index)  # Talent (15 rows)

# Write the final data to a text file in the required format with commas
output_txt_path_corrected = 'skill_silder_json.txt'

with open(output_txt_path_corrected, 'w', encoding='utf-8') as f:
    for key, value in final_data_corrected.items():
        # Ensure that each item is properly formatted with commas and quotes
        value_with_commas = ', '.join(value)
        f.write(f'{key}: [{value_with_commas},],\n')

print(f"Data successfully written to {output_txt_path_corrected}")
