import streamlit as st

st.set_page_config(page_title="Welcome", page_icon=":tada:", layout="centered")

st.title("Welcome to My Secure Streamlit App")
st.write("This is a simple Streamlit app with Cognito authentication, deployed on AWS ECS using CDK.")
