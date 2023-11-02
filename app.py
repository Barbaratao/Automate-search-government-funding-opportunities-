from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
import datetime
import os
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import os
import re
#######################################################
#download NIH funding opportunity 
#######################################################
# Initialize Chrome options
chrome_options = Options()
# Use ChromeDriverManager to get the ChromeDriver path
driver_path = ChromeDriverManager().install()

# Create a service object with the driver path
service = Service(driver_path)

driver = webdriver.Chrome(service=service, options=chrome_options.add_argument('--headless'))

driver.get("https://www.grants.gov/web/grants/search-grants.html")
time.sleep(10)
driver.switch_to.frame(driver.find_element(By.XPATH, "//*[@id='embeddedIframe']"))
driver.find_element(By.XPATH, "/html/body/table[1]/tbody/tr/td[3]/table[2]/tbody/tr[1]/td/a[2]").click()
time.sleep(10)
# Specify the directory where the downloaded files are located
download_directory = "C:\\Users\\Jun Tao\\Downloads\\"

# List all files in the directory and sort by modification time (newest first)
files = os.listdir(download_directory)
files.sort(key=lambda x: os.path.getmtime(os.path.join(download_directory, x)), reverse=True)
file_name = download_directory + files[0]



# Loop the data lines
with open(file_name, encoding='ISO-8859-1') as temp_f:
# get No of columns in each line
    col_count = [len(l.split(",")) for l in temp_f.readlines()]

# Generate column names (names will be 0, 1, 2, ..., maximum columns - 1)
column_names = [i for i in range(0, max(col_count))]

grant = pd.read_csv(file_name, sep=',', header=None, names=column_names)

grant.dropna(axis=1, how='all', inplace=True)

# Set the first row as the column names
grant.columns = grant.iloc[0]

# Drop the first row (which is now redundant)
grant = grant[1:]

# Reset the index after dropping the first-row
grant.reset_index(drop=True, inplace=True)

def extract_string_from_hyperlink(hyperlink):
# Split the string using the comma as a delimiter and return the second part
    parts = hyperlink.split(',')
    if len(parts) > 1:
        return parts[1]
    else:
        return hyperlink

# Apply the custom function to the column containing the hyperlinks
grant['OPPORTUNITY NUMBER'] = grant['OPPORTUNITY NUMBER'].apply(extract_string_from_hyperlink).str.replace(r'["\)]', '', regex=True)


# Update the run_date and design to run every other week
run_date = datetime.datetime(2022, 1, 1)
grant["POSTED DATE"]=pd.to_datetime(grant["POSTED DATE"])
grant["CLOSE DATE"]=pd.to_datetime(grant["CLOSE DATE"])
#only select grant opportunities that posted after the previous run_date
df=grant[grant["POSTED DATE"]>run_date]

#set up the due date
due_date=datetime.datetime(2024,1,1)
#only show the funding opportunities that expired after the due_date. 
df=df[df["CLOSE DATE"]>due_date]
#set keywords for selection, add your own keywords
keywords=["xx","xx"]
#set negative keywords to exclude funding opportunities
negative_keywords=["xx","xx"]

################################################################################################################
#select related funding opportunities 
#scraping funding opportunities from the NIH funding webpage 
#check similarity with research profile
#return top five funding opportunities 
################################################################################################################

#function to select_grant 

def select_grants(df, keywords, negative_keywords):
    # Create a boolean mask for rows containing keywords
    mask = df['OPPORTUNITY TITLE'].str.contains('|'.join(keywords), case=False, na=False)
    result = df[mask]

    # Create a mask for rows containing negative keywords
    mask1 = result['OPPORTUNITY TITLE'].str.contains('|'.join(negative_keywords), case=False, na=False)

    # Combine the positive and negative masks to filter the DataFrame
    final_df = result[~mask1]
    #select agency from NIH
    column_mask = final_df["AGENCY NAME"].str.startswith("National")
    final_df=final_df[column_mask]
    return final_df

final_df=select_grants(df,keywords, negative_keywords)
#call the function and return the dataframe with funding opportunities to meet your requirement
final_df.info()

#function to scrape the funding opportunity purpose

def scrape_nih_grants_data(opportunity_numbers):
    # Create an empty DataFrame to store the results
    results_df = pd.DataFrame(columns=['OPPORTUNITY NUMBER', 'section_text',"full_url"])

    for id_number in opportunity_numbers:
        try:
            # Initialize section_text in case the element is not found
            section_text = "Element not found"
            #depends on the website you are looking fore, the full_url should be revised as needed.
            if id_number[0] == "P":
                # Create the full URL for the specific ID number with "P"
                full_url = 'https://grants.nih.gov/grants/guide/pa-files/' + id_number + '.html'
            elif id_number[0] == "R":
                # Create the full URL for the specific ID number with "R"
                full_url = 'https://grants.nih.gov/grants/guide/rfa-files/' + id_number + '.html'
            else:
                print(f"Invalid opportunity number prefix for ID {id_number}. Can't determine the base URL.")
                continue  # Skip to the next ID

            # Send an HTTP GET request to the URL
            response = requests.get(full_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the element with a specific class, this section also need modification depends on the website you plan to scrape.
            div_element = soup.find('div', string=re.compile(r'(Notice of )?Funding Opportunity Purpose'))
            
            if div_element:
                section_text = div_element.find_next('p').get_text()
            
            # Create a dictionary with the data
            data_dict = {'OPPORTUNITY NUMBER': id_number, 'section_text': section_text,"full_url":full_url}
            
            # Append the dictionary to the DataFrame
            results_df = pd.concat([results_df, pd.DataFrame([data_dict])], ignore_index=True)

        except Exception as e:
            print(f"Error for ID {id_number}: {str(e)}")

    return results_df

#call the function 
text=scrape_nih_grants_data(final_df["OPPORTUNITY NUMBER"])



# Your research profile keywords and criteria, update your own keywords and weights
research_profile_criteria = {
    "epidemiology": 2,  # Assign a score (e.g., 1 to 5) to each keyword
    "disease prevention": 2,
    "public health": 3,
    "healthcare disparities": 4,
    "implementation": 2,
    "modeling":2,
    "HIV":5,
    "prevention":2,
    "opiod use":3,
    "substance use":2,
    "innovative technology":4,
    "artificial intelligence":4,
    "access to care":3,
    "minority":2,
    "underserved":1,
    "digital health":2
}

# Function to calculate similarity
def calculate_similarity(text,criteria):
    similarities = []
    for index1, row1 in text.iterrows():
        text1 = row1['section_text']
        text1 = text1.lower()   # Convert FOA text to lowercase for case-insensitive matching
        total_score = 0
        for keyword, score in criteria.items():
            if keyword in text1:
                total_score += score

        similarity_score = total_score

        similarities.append({
            "OPPORTUNITY NUMBER": row1["OPPORTUNITY NUMBER"],
            'text1': text1,
            'similarity': similarity_score,
            "full_url":row1["full_url"]
        })

    return similarities 

test2=calculate_similarity(text,research_profile_criteria)
test3=pd.DataFrame(test2)
sorted_df = test3.sort_values(by='similarity', ascending=False)
