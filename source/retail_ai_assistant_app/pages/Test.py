import streamlit as st
from utils.auth2 import authenticate_user

is_authenticated = authenticate_user()

if not is_authenticated:
    st.switch_page('app.py')

