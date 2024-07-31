import pandas as pd
import os
import json

def csvtojson():
    # Define the CSV file path
     # Define the base directory (adjust the path as necessary)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    csv_file_path = os.path.join(base_dir, 'assets', 'data', 'products.csv')

    # Read the CSV file
    df = pd.read_csv(csv_file_path)

    # Convert the 'featured' and 'promoted' columns to boolean
    df['featured'] = df['featured'].astype(bool)
    df['promoted'] = df['promoted'].astype(bool)

    # Extract the image name from the 'image' column
    df['image'] = df['image'].apply(lambda x: x.split('/')[-1])

    # Extract the last part of the URL from the 'url' column
    df['url'] = df['url'].apply(lambda x: x.split('/')[-1])

    # Replace NaN with empty strings for all columns
    df.fillna('', inplace=True)

    # Ensure 'related_items' is an empty list if the value is empty or NaN
    df['related_items'] = df['related_items'].apply(lambda x: [] if pd.isna(x) or x == '' else x)

    # Convert to JSON and save
    json_file_path = os.path.join(base_dir, 'assets', 'data', 'products.json')
    df.to_json(json_file_path, orient='records', lines=False)

    print(f"CSV file {csv_file_path} has been converted to JSON file {json_file_path}")
