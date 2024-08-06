import logging
import streamlit as st

@st.cache_resource
def get_logger(name):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Stream handler for Streamlit
        stream_handler = logging.StreamHandler()
        logger.addHandler(stream_handler)
        
    
    return logger