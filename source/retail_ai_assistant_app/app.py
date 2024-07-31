# app.py
import streamlit as st
from utils.auth2 import authenticate_user, get_cognito_login_url, get_cognito_logout_url, logout


def main():

    st.title("Streamlit App with ALB and Cognito Authentication")

    # Print headers
    st.write("Headers:")
    st.json(dict(st.context.headers))

    # Print cookies
    st.write("Cookies:")
    st.json(dict(st.context.cookies))

    is_authenticated = authenticate_user()

    if is_authenticated:
        st.write("Hello, you are logged in!")
        st.write("Authenticated User Info:")
        st.write(st.session_state.user_profile)

        if st.button('Logout'):
            logout()
    else:
        st.write("You are not authenticated.")
        login_url = get_cognito_login_url()
        st.markdown(f'<a href="{login_url}" target="_self"><button>Login with Cognito</button></a>', unsafe_allow_html=True)
      

if __name__ == '__main__':
    main()
