
import streamlit as st
# from authenticate import CognitoAuthenticator
import auth as authenticate

# # Initialize the authenticator once
# if 'authenticator' not in st.session_state:
#     st.session_state.authenticator = CognitoAuthenticator()
# if 'user_info' not in st.session_state:
#     st.session_state.user_info = None

# auth = st.session_state.authenticator

# Check authentication when user lands on the home page.
authenticate.set_st_state_vars()

def main():

    # Add login/logout buttons
    if st.session_state["authenticated"]:
        show_main_content()
        authenticate.button_logout()
    else:
        authenticate.button_login()
    
    # Print headers
    st.write("Headers:")
    st.json(dict(st.context.headers))

    # Print cookies
    st.write("Cookies:")
    st.json(dict(st.context.cookies))
    # if auth.check_auth():
    #     show_main_content()
    # else:
    #     login_url = auth.get_login_url()
    #     st.link_button("Login", login_url)
    #     st.stop()

def show_main_content():
    st.title(f"Welcome, {st.session_state.user_info['username']}!")
    st.write(f"Welcome, {st.session_state.user_info['email']}!")
    st.write("This is the protected content of your app")

    # if st.button('Logout'):
    #     auth.logout()

    # if st.button("Logout"):
    #     auth.logout()
    #     logout_url = auth.get_logout_url()
    #     st.write(f"Logging out... You will be redirected to the logout page.")
        
    # # logout_url = auth.get_logout_url()
    # # st.link_button("Logout", logout_url)

if __name__ == "__main__":
    main()
