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


driver.get("https://www.grants.gov/search-grants.html")

# Wait for the <select> element by its ID for "Posted Date Range" to be present
wait = WebDriverWait(driver, 10)
dropdown = wait.until(EC.presence_of_element_located((By.ID, 'dateRange')))

# Wrap the WebElement in a Select object
select_element = Select(dropdown)
dropdown.click()
time.sleep(5)
# Select the option by visible text
#select_element.select_by_visible_text("Posted Date - Last 2 Weeks")
select_element.select_by_value("14")
# Find and click the "Update Date Range" button
update_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Update Date Range']")))
update_button.click()

# Step 1: Wait for the page to load new content
time.sleep(5)  # Adjust the sleep time as needed based on the page's response time

data = []

while True:
    try:
        # Wait for the table to be visible\
        table_class = "usa-table usa-table--stacked usa-table--compact margin-0 width-full usa-table--striped margin-top-2"
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, table_class.replace(" ", "."))))
        table = driver.find_element(By.CLASS_NAME, table_class.replace(" ", "."))
        rows = table.find_elements(By.TAG_NAME, 'tr')

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            row_data = [col.text for col in cols]
            # Assuming the href is in the first column, modify as needed
            href_element = cols[0].find_element(By.TAG_NAME, 'a') if cols else None
            href = href_element.get_attribute('href') if href_element else None
            row_data.append(href)
            data.append(row_data)

        # Find the 'Next' button
        next_button = driver.find_element(By.XPATH, "//span[contains(@class, 'usa-pagination__link-text') and contains(text(), 'Next')]")

        # Check if the 'Next' button is enabled
        if 'disabled' in next_button.get_attribute('class'):
            break

        # Click the 'Next' button
        next_button.click()

    except NoSuchElementException:
        print("No more pages or the 'Next' button is not found.")
        break
    except TimeoutException:
        print("Timed out waiting for the page to load.")
        break
    finally:
        # Close the browser
        driver.quit()

# Filter out rows that are empty lists
grant = pd.DataFrame(data)
grant=grant.dropna(how="any")
# Filter out rows that are empty lists 
# Get the name of the last column
last_column = grant.columns[-2]

# Drop the last column
grant = grant.drop(columns=[last_column]) 
grant.columns=["OPPORTUNITY NUMBER","OPPORTUNITY TITLE", "AGENCY NAME","STATUS", "POST DATE","URL"]

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
