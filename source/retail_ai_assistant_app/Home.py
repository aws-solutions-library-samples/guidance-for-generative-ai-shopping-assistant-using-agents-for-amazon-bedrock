# app.py
import streamlit as st
from utils.authenticate import authenticate_user, get_cognito_login_url, get_cognito_logout_url, logout
from utils.temp import csvtojson
from utils.studio_style import apply_studio_style, get_background
from utils.studio_style import keyword_label


def main():

    # if st.button('csvtojson'):
    #     csvtojson()

    # Add a title and description
    st.title("Welcome to AI Shopping Assistant")

    # Create two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("""
        Our AI Shopping Assistant is here to revolutionize your online shopping experience! 
        Powered by advanced AI technologies, including Amazon Bedrock and large language models, 
        our assistant is designed to understand your needs and preferences, providing personalized 
        product recommendations and answering your questions in real-time.

        Key Features:
        - Personalized product recommendations
        - Real-time question answering about products
        - Natural language understanding for a conversational experience
        - Integration with a vast product database for accurate information

        To get started, please log in and explore the power of AI-assisted shopping!
        """)

    with col2:
        st.image("assets/images/shopping_agent.png", caption="AI Shopping Assistant")


    is_authenticated = authenticate_user()

    if is_authenticated:
        st.write("Hello, you are logged in!")
        st.write("Authenticated User Info:")
        st.write(st.session_state.user_profile)

        if st.button('Logout'):
            logout()
    else:
        #st.write("You are not authenticated.")
        login_url = get_cognito_login_url()
        st.markdown(f'<a href="{login_url}" target="_self"><button class="linkButton">Login with Cognito</button></a>', unsafe_allow_html=True)

    # Print headers
    # st.write("Headers:")
    # st.json(dict(st.context.headers))

    # # Print cookies
    # st.write("Cookies:")
    # st.json(dict(st.context.cookies))
      

if __name__ == '__main__':
    get_background()
    main()
