# app.py
import streamlit as st
from utils.authenticate import authenticate_user, get_cognito_login_url
from utils.studio_style import get_background

st.set_page_config(
    page_title=f"Retail AI Shopping Agent",
    page_icon="🛍️",
    layout='wide'
)


def main():
    st.title("Welcome to AI Shopping Assistant")

    # Create two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""

        This AI Assitant is generative AI-powered shopping assistant that enhances customer experience and drives sales through context-aware, AI-powered interactions. 

        #### Key Agent Features:
        - Personalized, Context-Aware Conversations
        - Alternate & Related Product Recommendations
        - Dynamic Side-by-Side Product Comparisons
        - Cart Management & Placing Order
        - Automated Email Confirmations

        #### How It Works
        The Shopping Agent is built using [Agents for Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html) that uses Anthropic's Claude Sonnet 3 model to interpret user queries and orchestrate multi-step tasks for an efficient shopping experience. 
        - It integrates with a [Knowledge Base for Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-bases.html) to embed product catalog details and uses [Amazon OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html) for vector search.
        - An Action Group that utilizes AWS Lambda function with OpenAPI Schema to manage API operations such as order creation, inventory checks, and sending email confirmations. 

        """)    
    with col2:
        st.image("assets/images/Shopping_Agent.png", caption="AI Shopping Assistant")


    is_authenticated = authenticate_user()

    if not is_authenticated:
        st.write("To get started, please log in and explore the power of AI-assisted shopping today!")
        login_url = get_cognito_login_url()
        st.markdown(f'<a href="{login_url}" target="_self"><button class="linkButton">Login with Cognito</button></a>', unsafe_allow_html=True)


if __name__ == '__main__':
    get_background()
    main()
