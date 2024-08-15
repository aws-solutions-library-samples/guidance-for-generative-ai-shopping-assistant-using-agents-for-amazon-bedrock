# utils/product_service.py

import json
import requests
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from a .env file
load_dotenv()

class ProductService:
    def __init__(self, _api_url, _api_key, _logger):
        self.api_url = _api_url
        self.api_key = _api_key
        self.logger = _logger

    def get_product_details(self, product_id):
        try:
            api_key_json = {"api_key":self.api_key}
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.api_key
            }
            response = requests.get(f"{self.api_url}/products/id/{product_id}", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching product details: {e}")
            return None

