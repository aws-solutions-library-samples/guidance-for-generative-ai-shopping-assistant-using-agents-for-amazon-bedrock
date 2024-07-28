# app.py
import streamlit as st
from config import get_authenticator

# Get the authenticator
authenticator = get_authenticator()


## login auth with cognito    
def login():
    is_logged_in = authenticator.login()
    #if not logged in, stop the app and keep in login page
    if not is_logged_in:
        st.stop()

## logout auth with cognito    
def logout():
    authenticator.logout()  
    #redirect to login page
    login()


def display_ui():
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Logout"):
            logout()
    
    # Show the main content
    with col1:
        # Your app logic here
        st.title("Welcome to the App")
        user_name = authenticator.get_username()
        st.write(f"Welcome, {user_name}!")
        st.write("This is the protected content of your app")
        
        # Add more of your app content here
        st.write("Here's some more protected content...")




# Main application logic
if __name__ == "__main__":

    # Auth with cognito and redirect to login page if not logged in
    login()

    display_ui()
