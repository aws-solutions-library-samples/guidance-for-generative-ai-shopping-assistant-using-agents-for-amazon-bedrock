# utils/product_service.py

import os
import requests
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from a .env file
load_dotenv()

class ProductService:
    def __init__(self, _api_url, _logger):
        self.api_url = _api_url
        self.logger = _logger

    def get_product_details(self, product_id):
        try:
            response = requests.get(f"{self.api_url}/products/id/{product_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching product details: {e}")
            return None

