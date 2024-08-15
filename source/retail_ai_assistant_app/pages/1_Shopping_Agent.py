import streamlit as st
import re, io, json, os
import pandas as pd
import shutil
import uuid
from utils.logger import get_logger
from utils.authenticate import authenticate_user
from utils.studio_style import apply_studio_style, get_background
from utils.studio_style import keyword_label
from utils.helper import resize_image, encode_image
from utils.config import Config
from utils.bedrock import BedrockAgent
from utils.product_service import ProductService
from datetime import datetime


st.set_page_config(
    page_title=f"Retail AI Shopping Agent",
    page_icon="🛍️",
    layout='wide'
)

def reset_chat_directory():
    chat_dir = st.session_state.chat_directory
    
    # If the directory exists, delete it
    if os.path.exists(chat_dir):
        shutil.rmtree(chat_dir)
    
    # Create a new chat directory
    os.makedirs(chat_dir)

def load_agent_session_state():
    # Send current time for time awareness to LLM
    current_time = datetime.now()

    if 'selected_user_profile' in st.session_state and st.session_state.selected_user_profile is not None:
        selected_user_profile = st.session_state.selected_user_profile 
        
        address = selected_user_profile['addresses'][0]
        address_str = ', '.join([f"{key}: {value}" for key, value in address.items()])

        st.session_state.agent_session_state = {
            "promptSessionAttributes": {
                'currentDate': str(current_time),
                'email': selected_user_profile['email'],
                "first_name": selected_user_profile['first_name'],
                "last_name": selected_user_profile['last_name'],
                "address": address_str,
                "age": str(selected_user_profile['age']),
                "gender": selected_user_profile['gender'],
                "persona": selected_user_profile['persona'],
                "discount_persona": selected_user_profile['discount_persona']
            },
            "sessionAttributes": {
                "username": selected_user_profile['username'],
                "email": selected_user_profile['email']
            }
        }
    else:
        st.session_state.agent_session_state = {
            "promptSessionAttributes": {
                'currentDate': str(current_time)
            }
        }

def initialize_session_state():
    st.session_state.welcome_message = "Hello! Welcome to AnyCompanyCommerce. I'm your AI shopping assistant here to help you find products that match your needs and interests. How can I assist you today?"
    st.session_state.chat_directory = os.path.join("temp", "chat")
    if 'messages' in st.session_state and st.session_state.messages and  len(st.session_state.messages) > 1:
        GetAnswers(' ', st.session_state.session_id, 
                    st.session_state.bedrock_agent, 
                    st.session_state.config.SHOPPING_AGENT_ID, 
                    st.session_state.config.SHOPPING_AGENT_ALIAS_ID,
                    st.session_state.agent_session_state, None, end_session=True)
        
    st.session_state.total_input_tokens=0
    st.session_state.total_output_tokens=0
    st.session_state.total_invoke_agent=0
        
    if 'config' not in st.session_state:
        st.session_state.config = Config()
    if 'logger' not in st.session_state:
        st.session_state.logger = get_logger('retail-ai-agent')
    if 'bedrock_agent' not in st.session_state:
        st.session_state.bedrock_agent = BedrockAgent(st.session_state.config.SESSION, st.session_state.logger)
    if 'product_service' not in st.session_state:
        st.session_state.product_service = ProductService(st.session_state.config.API_URL, st.session_state.config.API_KEY, st.session_state.logger)
    if 'total_input_tokens' not in st.session_state:
        st.session_state.total_input_tokens =0
    if 'total_output_tokens' not in st.session_state:
        st.session_state.total_output_tokens =0
    if 'total_invoke_agent' not in st.session_state:
        st.session_state.total_invoke_agent =0

    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.chat_image = None
    st.session_state.trace = {}
    st.session_state.email_confirmation=''
    st.session_state.messages.append({"role": "assistant", "content": st.session_state.welcome_message})
    st.session_state.selected_product = None
    st.session_state.user_prompt = None
    st.session_state.buy_product = None
    st.session_state.user_action = None
    st.session_state.shipping_details_provided = None
    st.session_state.answer = None
    st.session_state.cart = []

    load_agent_session_state()
    reset_chat_directory()

@st.cache_data
def load_random_user_profiles():
    file_path = os.path.join('.','assets','data', 'user-profiles.json')
    try:
        with open(file_path, 'r') as file:
            user_profiles = json.load(file)
        return user_profiles
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: The file {file_path} contains invalid JSON.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

def GetAnswers(query, session_id, assistant, agent_id, agent_alias_id, agent_session_state, base64_image= None, end_session: bool = False):

    st.session_state.total_invoke_agent += 1
    answer = assistant.invoke_agent(agent_id, agent_alias_id, session_id, agent_session_state, query, base64_image, end_session)
    st.session_state.answer = answer

    return answer

def extract_email_and_body(trace):
    action_group_input = trace['invocationInput']['actionGroupInvocationInput']
    if action_group_input['apiPath'] == '/orders/{orderId}/sendEmail':
        request_body = action_group_input['requestBody']['content']['application/json']
        email = next((item['value'] for item in request_body if item['name'] == 'email'), None)
        email_body = next((item['value'] for item in request_body if item['name'] == 'emailBody'), None)
        return email, email_body
    return None, None

def reformat_product_output_list(response):
    compare_products=None

    products_matches = re.findall(r'(?s)<products>(.*?)</products>', response, re.DOTALL)
    related_products_matches = re.findall(r'(?s)<relatedProducts>(.*?)</relatedProducts>', response, re.DOTALL)
    compare_match = re.search(r'(?s)<compare>(.*?)</compare>', response, re.DOTALL)

    # Parse CSV content into lists
    products_list = [pd.read_csv(io.StringIO(match)).to_dict(orient='records') for match in products_matches]
    related_products_list = [pd.read_csv(io.StringIO(match)).to_dict(orient='records') for match in related_products_matches]

    if compare_match:
        csv_content = compare_match.group(1)
        if csv_content:
            compare_products = csv_content.strip()

    # Remove both <products> and <relatedProducts> tags and their contents from the response
    response = re.sub(r'(?s)<products>(.*?)</products>', '', response, flags=re.DOTALL)
    response = re.sub(r'(?s)<relatedProducts>(.*?)</relatedProducts>', '', response, flags=re.DOTALL)
    response = re.sub(r'(?s)<compare>(.*?)</compare>', '', response, flags=re.DOTALL)

    return response.strip(), products_list, related_products_list, compare_products

def display_product_list_2(products_list):
    products_history = ""

    for products in products_list:
        if not products:
            continue

        i = 1
        for product in products:
            if isinstance(product, dict) and 'productId' in product:
                product_id = product['productId']
            else:
                product_id = next(iter(product.keys())) # Assume first key as product_id if header not in json

            try:
                product_details = st.session_state.product_service.get_product_details(product_id)
                if product_details:
                    products_history += f"""
                | <img src="{product_details["image"]}" width="100" alt="{product_details["name"]}"> | {i}. **{product_details["name"]}** | Price: ${product_details["price"]} |
                """

                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.image(product_details['image'], width=150)
                    with col2:
                        st.write(f"{i}. {product_details['name']}")
                        st.write(f"${product_details['price']}")
                        st.button(f"View Details", key=f"show_{product_details['id']}", on_click=show_product, args=(product_details,))
                    
                    i += 1
            except Exception as e:
                print(f"An unexpected error occurred: {str(e)}")
    
    return products_history

    
def display_product_list(products):
    products_history= f""" """
    for i, product in enumerate(products, 1):
        try:
            product = st.session_state.product_service.get_product_details(product['product_id'])
            if product:
                products_history += f"""
            | <img src="{product["image"]}" width="100" alt="{product["name"]}"> | {i}. **{product["name"]}** | Price: ${product["price"]} |
            """

                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(product['image'], width=150)
                with col2:
                    st.write(f"{i}. {product['name']}")
                    st.write(f"${product['price']}")
                    st.button(f"View Details", key=f"show_{product['id']}", on_click=show_product, args=(product,))
        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")
        
    return products_history

def display_compare(text):

    df = pd.read_csv(io.StringIO(text))

    if not df.empty:
        def create_markdown_table(df):
            # Create the header
            markdown = "| " + " | ".join(df.columns) + " |\n"
            markdown += "|" + "|".join(["---" for _ in df.columns]) + "|\n"
        # Add each row
            for _, row in df.iterrows():
                row_md = []
                for col in df.columns:
                    if col == 'Image':
                        row_md.append(f'<img src="{row[col]}" width="100">')
                    else:
                        row_md.append(str(row[col]))
                markdown += "| " + " | ".join(row_md) + " |\n"
            return markdown
                
        
        product_list=[]
        # Display dataframe with buttons for each action
        for index, row in df.iterrows():
            product = {
            'product_id': row['Product ID'],
            'name': row['Product Name'],
            "image": row['Image'],
            "price": row['Price'],
            "promoted": False
            }
            product_list.append(product)

        # Reorder columns
        column_order = ['Product Name', 'Image', 'Price'] + [col for col in df.columns if col not in [ 'Product ID', 'Product Name', 'Image', 'Price']]
        df = df[column_order]
        # Display the dataframe
        st.dataframe(
        df,
        column_config={
            "Image": st.column_config.ImageColumn("Product Image", width="medium"),
            "Price": st.column_config.TextColumn("Price", width="small"),
        },
        hide_index=True,
        use_container_width=True,
        )

        display_product_list(product_list)
        
        st.session_state.messages.append({"role": "assistant", "content": create_markdown_table(df)})
                          
    return df   


def add_prompt(prompt, file_path: None ):
    if prompt:
        st.session_state.user_action = 'ADD_PROMPT'
        st.session_state.user_prompt = prompt
        st.session_state.chat_image = file_path

def load_sample_prompts():
    st.write('Click to try Sample Prompts:')
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1,2,1,1,1,1,1])
    with col1:
        text = 'Good quality tents for camping trip'
        st.button(text, key="prompt_1", on_click=add_prompt, args=(text,None,))
    with col2:
        text = 'What kind of outfit should I wear on my first day at New York Times?'
        st.button(text, key="prompt_2", on_click=add_prompt, args=(text,None,))
    with col3:
        text = 'Picnic snacks for 4 persons'
        st.button(text, key="prompt_3", on_click=add_prompt, args=(text,None,))
    with col4:
        # Read recipe
        recipe = ''  
        data_path = os.path.join(os.path.dirname(__file__), "..", "assets", "data", "recipe.txt")
        with open(f"{data_path}", encoding='utf-8') as f:
            recipe = f.read()
        text = 'Cook Mediterranean Salad'
        if recipe:
            prompt = f"""Help me find any products available to buy for below recipe:\n\n
            
            {recipe}"""
        else:
            prompt= text
        st.button(text, key="prompt_4", on_click=add_prompt, args=(prompt,None,))
    with col5:
        # Set grocery list image
        file_path = os.path.join(os.path.dirname(__file__), "..", "assets", "data", "grocery_list.jpeg")
        text = 'Buy grocery items'
        st.button(text, key="prompt_5", on_click=add_prompt, args=(text,file_path,))
    with col6:
        text = 'Moving to new apartment'
        st.button(text, key="prompt_6", on_click=add_prompt, args=(text,None,))
    with col7:
        text = 'Gift for wedding anniversary'
        st.button(text, key="prompt_7", on_click=add_prompt, args=(text,None,))
    

def show_product(product):
    st.session_state.selected_product = product
    user_query = f'View details for **{product['name']}**'
    st.session_state.messages.append({"role": "user", "content": user_query})

def buy_product(product,quantity):
    quantity = st.session_state[f"quantity_{product['id']}"]
    product_to_buy =  {
                'product_id': product['id'],
                'product_name': product['name'],
                'current_stock': product['current_stock'],
                'quantity': quantity
                }
    st.session_state.buy_product = product_to_buy
    st.session_state.user_action = 'BUY_PRODUCT'
    user_query = f"Buy product : **{ product['name']}, Quantity: {quantity}**"
    st.session_state.messages.append({"role": "user", "content": user_query})

def add_product(product, quantity):
    quantity = st.session_state[f"quantity_{product['id']}"]
    product_to_buy =  {
                'product_id': product['id'],
                'product_name': product['name'],
                'current_stock': product['current_stock'],
                'quantity': quantity
                }
    st.session_state.buy_product = product_to_buy
    st.session_state.user_action = 'ADD_PRODUCT'
    user_query = f"Add product { product['name']} to order, Quantity: {quantity}"
    st.session_state.messages.append({"role": "user", "content": user_query})

# The JSON object representing the shipping address structure
shipping_address_structure = {
    "email": "",
    "firstName": "",
    "lastName": "",
    "address": "",
    "city": "",
    "zipCode": "",
    "state": "",
    "country": ""
}

def submit_callback():
    form_data = {
        "Email": st.session_state.email,
        "First Name": st.session_state.first_name,
        "Last Name": st.session_state.last_name,
        "Address": st.session_state.address,
        "City": st.session_state.city,
        "Zip Code": st.session_state.zip_code,
        "State": st.session_state.state,
        "Country": st.session_state.country
    }

    # Format the form data as a string with key-value pairs, using HTML <br> tags for line breaks
    formatted_data = "<br>".join(f"{key}: {value}" for key, value in form_data.items())
    
    formatted_details = f"""
        Shipping address details: <br>
        {formatted_data}
        """

    st.session_state.messages.append({"role": "user", "content": formatted_details})
    st.session_state.shipping_details_provided = form_data

def create_shipping_form():
    with st.form("shipping_address_form"):
        st.write("## Shipping Address")

        email = 'john.doe@xyz.com'
        address_info = {
            'first_name': 'John',
            'last_name': 'Doe',
            'address1': 'ABC X street',
            'state': 'Stockholm',
            'city': 'Stockholm',
            'zipcode': '336647',
            'country': 'Sweden'
        }
        
        if st.session_state.selected_user_profile and st.session_state.selected_user_profile != '':
            address = st.session_state.selected_user_profile['addresses'][0]
            email = st.session_state.selected_user_profile['email']

            address_info.update({
            'first_name': address.get('first_name', 'John'),
            'last_name': address.get('last_name', 'Doe'),
            'address1': address.get('address1', 'ABC X street'),
            'state': address.get('state', 'Stockholm'),
            'city': address.get('city', 'Stockholm'),
            'zipcode': address.get('zipcode', '336647'),
            'country': address.get('country', 'Sweden')
        })

        # Email in a single column
        st.text_input("Email", key="email", value=st.session_state.get('email', email))

        # Create two columns for the form
        col1, col2 = st.columns(2)

        # First Name and Last Name in the same row
        with col1:
            st.text_input("First Name", key="first_name", value=st.session_state.get('first_name', address_info['first_name']))
        with col2:
            st.text_input("Last Name", key="last_name", value=st.session_state.get('last_name', address_info['last_name']))

        # Address in a single column
        st.text_input("Address", key="address", value=st.session_state.get('address', address_info['address1']))

        # City and Zip Code in the same row
        with col1:
            st.text_input("City", key="city", value=st.session_state.get('city', address_info['city']))
        with col2:
            st.text_input("Zip Code", key="zip_code", value=st.session_state.get('zip_code', address_info['zipcode']))

        # State and Country in the same row
        with col1:
            st.text_input("State", key="state", value=st.session_state.get('state', address_info['state']))
        with col2:
            st.text_input("Country", key="country", value=st.session_state.get('country', address_info['country']))

        # Center the submit button and give it a custom width
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.form_submit_button("Submit", on_click=submit_callback, use_container_width=True)

def upload_image():
    if 'chat_file' in st.session_state:
        uploaded_file = st.session_state.chat_file
        file_name = uploaded_file.name
        file_path = os.path.join(st.session_state.chat_directory, file_name)
        # Save the file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.chat_image = file_path

    
def load_demo():

    chat_container = st.container(height=600)
    
    for message in st.session_state.messages:
        chat_container.chat_message(message["role"]).markdown(message["content"], unsafe_allow_html=True)
    
    if  len(st.session_state.messages) <= 1:
        with chat_container.chat_message("assistant"):
            load_sample_prompts()
    
    user_query = st.chat_input(placeholder="Ask me anything!", max_chars=750)

    st.sidebar.file_uploader("Upload Image to Chat", type=["jpg", "jpeg", "png"], key="chat_file", on_change = upload_image)

    encoded_image = None
    if st.session_state.chat_image:
        encoded_image = encode_image(st.session_state.chat_image)
        # Add image to messages as HTML tag
        img_html = f'<img src="data:image/jpeg;base64,{encoded_image}" alt="Uploaded Image" style="max-width: 300px; max-height: 300px;"/>'
        st.session_state.messages.append({"role": "user", "content": img_html})
        chat_container.chat_message("user").markdown(img_html, unsafe_allow_html=True)
        st.session_state.chat_image = None

    # Add Sample prompt
    if st.session_state.user_prompt:
        user_query = st.session_state.user_prompt
        st.session_state.user_prompt = None
    
    if user_query:
        st.session_state.selected_product = None
        st.session_state.buy_product = None

        st.session_state.messages.append({"role": "user", "content": user_query})
        chat_container.chat_message("user").write(user_query)
            
        with chat_container.chat_message("assistant"):
            # Add a spinner to show loading state
            with st.spinner('...'):
                response = GetAnswers(user_query, st.session_state.session_id, st.session_state.bedrock_agent, 
                                       st.session_state.config.SHOPPING_AGENT_ID, st.session_state.config.SHOPPING_AGENT_ALIAS_ID,
                                       st.session_state.agent_session_state, encoded_image)

                formatted_response, products, related_products, compare_products = reformat_product_output_list(response["output_text"])
                st.markdown(formatted_response, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": formatted_response})

                if products:
                    # Add a separator
                    st.markdown("---")
                    # Display the products as a list
                    st.write("Suggested Products:")
                    products_history= display_product_list_2(products)
                    st.session_state.messages.append({"role": "assistant", "content": products_history})
                
                if related_products:
                    # Add a separator
                    st.markdown("---")
                    # Display the products as a list
                    st.write("Products you might like:")
                    related_products_history= display_product_list_2(related_products)
                    st.session_state.messages.append({"role": "assistant", "content": related_products_history})
                    
                if compare_products:
                    display_compare(compare_products)

                st.session_state.trace = response["trace"]
    
    # Display selected product details
    if st.session_state.selected_product:
        product= st.session_state.selected_product
        with chat_container.chat_message("assistant"):  
            with st.spinner('...'):
                # print(product)
                if product: 
                    col1, col2 = st.columns([1.5, 1])
                    with col1:
                        st.image(product['image'], width=300)
                        st.write(f"<small>{product['description']}</small>", unsafe_allow_html=True)
                    with col2:
                        st.write(f"#### {product['name']}")
                        st.write(f"<small>Category: {product['category'].capitalize()} | Style: {product['style'].capitalize()}</small>", unsafe_allow_html=True)
                        st.write(f"${product['price']:.2f}")
                        if 'promoted' in product and product['promoted'] == "True":
                            st.write("🔥 **Promoted Item**")
                        if product['current_stock'] > 0:
                            with st.form('Order Item'):
                                col1, col2, col3 = st.columns([1, 0.5, 1])
        
                                with col1:
                                    quantity = st.number_input("Quantity", min_value=1, max_value=product['current_stock'], value=1, step=1, key=f"quantity_{product['id']}", format="%d")
                                
                                with col2:
                                    st.write("")  # This empty write is used to align the buttons properly
                                
                                with col3:
                                    st.write("")  # This empty write is used to align the buttons properly
                                
                                col1, col2, col3 = st.columns([1, 0.5, 1])
                                
                                with col1:
                                    st.form_submit_button("Add to Cart", on_click=add_product, disabled=(quantity < 1 or quantity > product['current_stock']), args=(product, quantity))
                                   
                                with col2:
                                    st.write("")  # This empty write is used to align the buttons properly
                                
                                with col3:
                                    st.form_submit_button("Buy Now",  on_click=buy_product, disabled=(quantity < 1 or quantity > product['current_stock']), args=(product, quantity))
                                    

                        else:
                            st.write("**Out of Stock**")
                        st.write(f"<small>Current Stock: {product['current_stock']} units</small>", unsafe_allow_html=True)


                    if product['aliases']:
                        st.write("<small>**Also known as:** " + ", ".join(product['aliases']) + "</small>", unsafe_allow_html=True)
                    
                    # Add exploration to message history
                    selected_content = f"""
                    <img src="{product['image']}" width="300" alt="{product['name']}"> 

                    #### {product['name']}

                    Category: {product['category'].capitalize()} | Style: {product['style'].capitalize()}  
                    {'🔥 **Promoted Item**' if 'promoted' in product and product['promoted'] == "True" else ''}

                    Price: ${product['price']:.2f}

                    Current Stock: {product['current_stock']} units

                    Description: 
                    {product['description']}
                    """
                    if product['aliases']:
                        selected_content += f"\n\n**Also known as:** {', '.join(product['aliases'])}"
                    
                    st.session_state.messages.append({"role": "assistant", "content": selected_content})
                else:
                    error = 'Apologies, there seems to be temporary issues in getting product details at the moment. Please try again later.'
                    st.session_state.messages.append({"role": "assistant", "content": error})

    if st.session_state.buy_product:
        product_to_buy = st.session_state.buy_product
        product_query= f"""
                <product_details>
                {json.dumps(product_to_buy, indent=2)}
                </product_details>
            """
        if st.session_state.user_action == 'BUY_PRODUCT':
            query = f"Add product { product_to_buy['product_name']} to cart. Place Order. \n{product_query}"
        else:
            query = f"Add product { product_to_buy['product_name']} to cart. \n{product_query}. \n Search catalog for complementary products."
        
        if st.session_state.shipping_details_provided is not None:
            data = st.session_state.shipping_details_provided
            query+= f"""

                <shipping_address>
                {json.dumps(data, indent=2)}
                </shipping_address>
            """

        with chat_container.chat_message("assistant"):
            # Add a spinner to show loading state
            with st.spinner('...'):
                if st.session_state.shipping_details_provided is None and st.session_state.user_action == 'BUY_PRODUCT':
                    st.markdown("Please provide your shipping address details:")
                    # Use a container with custom width for the form
                    with st.container():
                        _, col, _ = st.columns([1, 2, 1])  # This creates a centered column
                        with col:
                            create_shipping_form()
                else:
                    st.session_state.buy_product = None
                    response = GetAnswers(f"{query}", st.session_state.session_id, st.session_state.bedrock_agent, 
                                       st.session_state.config.SHOPPING_AGENT_ID, st.session_state.config.SHOPPING_AGENT_ALIAS_ID,
                                       st.session_state.agent_session_state,None)
                    
                    # print(response["output_text"])

                    formatted_response, products, related_products, compare_products = reformat_product_output_list(response["output_text"])
                    st.markdown(formatted_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": formatted_response})

                    if products:
                        # Add a separator
                        st.markdown("---")
                        # Display the products as a list
                        st.write("Suggested Products:")
                        products_history= display_product_list_2(products)
                        st.session_state.messages.append({"role": "assistant", "content": products_history})
                        
                    
                    if related_products:
                        # Add a separator
                        st.markdown("---")
                        # Display the products as a list
                        st.write("Products you might like:")
                        related_products_history= display_product_list_2(related_products)
                        st.session_state.messages.append({"role": "assistant", "content": related_products_history})
        
                    st.session_state.trace = response["trace"]

            


def load_trace():
    trace_type_headers = {
    "preProcessingTrace": "Pre-Processing",
    "orchestrationTrace": "Orchestration",
    "postProcessingTrace": "Post-Processing"
    }
    trace_info_types = ["invocationInput", "modelInvocationInput", "modelInvocationOutput", "observation", "rationale"]

    st.subheader("Trace")

    # Show each trace types in separate sections
    for trace_type in trace_type_headers:
        st.write(trace_type_headers[trace_type])

        # Organize traces by step similar to how it is shown in the Bedrock console
        if trace_type in st.session_state.trace:
            trace_steps = {}
            for trace in st.session_state.trace[trace_type]:
                # print(trace)
                # Each trace type and step may have different information for the end-to-end flow
                for trace_info_type in trace_info_types:
                    if trace_info_type in trace:
                        trace_id = trace[trace_info_type]["traceId"]
                        if trace_id not in trace_steps:
                            trace_steps[trace_id] = [trace]
                        else:
                            trace_steps[trace_id].append(trace)
                        break

            # Show trace steps in JSON similar to the Bedrock console
            for step_num, trace_id in enumerate(trace_steps.keys(), start=1):
                with st.expander("Trace Step " + str(step_num), expanded=False):
                    for trace in trace_steps[trace_id]:
                        trace_str = json.dumps(trace, indent=2)
                        st.code(trace_str, language="json", line_numbers=trace_str.count("\n"))
                        # st.json(trace_str)

                        # Sum input and output tokens
                        if 'modelInvocationOutput' in trace:
                            usage = trace['modelInvocationOutput'].get('metadata', {}).get('usage', {})
                            st.session_state.total_input_tokens += usage.get('inputTokens', 0)
                            st.session_state.total_output_tokens += usage.get('outputTokens', 0)
                        
                        if 'invocationInput' in trace and 'actionGroupInvocationInput' in trace['invocationInput']:
                            email, email_body = extract_email_and_body(trace)
                            if email and email_body:
                                # print("Email body:", email_body)
                                st.session_state.email_confirmation = email_body
                              
        else:
            st.text("None")

def load_cost():
    input_token_cost = st.session_state.total_input_tokens * (st.session_state.config.MODEL_INPUT_TOKEN_PRICE/1000)
    output_token_cost = st.session_state.total_output_tokens * (st.session_state.config.MODEL_OUTPUT_TOKEN_PRICE/1000)

    total_cost = input_token_cost + output_token_cost

    st.markdown('### Model Cost for current Session')
    st.markdown (f"Total Agent Invoke Count: **{st.session_state.total_invoke_agent}**")

    st.markdown("""
        | Token Type      | Total Tokens | Cost [USD] |
        |-----------------|--------------|------------|
        | Input Tokens    | {total_input_tokens} | ${input_token_cost:.5f} |
        | Output Tokens   | {total_output_tokens} | ${output_token_cost:.5f} |
        | **Total Cost**  |              | **${total_cost:.5f}** |
        """.format(
            total_input_tokens=st.session_state.total_input_tokens,
            input_token_cost=input_token_cost,
            total_output_tokens=st.session_state.total_output_tokens,
            output_token_cost=output_token_cost,
            total_cost=total_cost
        ))

def load_session():
    st.write(f"Session ID: {st.session_state.session_id}")

    user_profiles = load_random_user_profiles()

    if user_profiles is not None and user_profiles != '':
        # Create a list of user options
        user_options = [""] + [f"ID: {user['id']} - AGE: {user['age']}, GENDER: {user['gender']}, PERSONA: {user['persona']}, DISCOUNT: {user['discount_persona']}" for user in user_profiles]
    else:
        user_options = [""]

    # Add a dropdown to select a user
    st.selectbox('Select a persona:', user_options, key='user_dropdown', on_change=on_user_change)
    
    if 'agent_session_state' in st.session_state and st.session_state.agent_session_state:
        st.json(st.session_state.agent_session_state)

def on_user_change():

    user_profiles = load_random_user_profiles()
    selected_user = st.session_state.user_dropdown
    # Display the selected user's information
    if selected_user and selected_user != "":
        # Extract the ID from the selected option
        selected_user_id = selected_user.split(" - ")[0].split(": ")[1]
        # Find the full user profile based on the ID
        st.session_state.selected_user_profile = next((user for user in user_profiles if str(user['id']) == selected_user_id), None)
    else:
        st.session_state.selected_user_profile = None
    initialize_session_state()



def main():
    
        
    col1, col2,  = st.columns([2,1])
    with col1:
        st.write(' '.join(formatted_labels), unsafe_allow_html=True)

    with col2:
        if st.button("Clear message history"):
            st.session_state.selected_user_profile = None
            st.session_state.user_dropdown = ""
            st.session_state.chat_image = None
            initialize_session_state()
    
    # Initialize the messages and assistant object using session state
    if "messages" not in st.session_state or "bedrock_agent" not in st.session_state:
        st.session_state.selected_user_profile = None
        st.session_state.user_dropdown = ""
        initialize_session_state()


    chat_demo, session, trace, cost  = st.tabs(["Assistant", "Agent Session State", "Trace", 'Model Cost'])
    with session:
        load_session()
    with chat_demo:
        load_demo()
    with trace:
        load_trace()
    with cost:
        load_cost()

    if st.session_state.email_confirmation:
        st.write(st.session_state.email_confirmation)
    



if __name__ == '__main__':

    is_authenticated = authenticate_user()
    if  not is_authenticated:
        st.switch_page('Home.py')
    
    agent_title= '🛍️Retail AI Shopping Agent'
    st.title(agent_title)
    
    keywords = [f'Amazon Bedrock Agent: Anthropic Claude Sonnet 3', 'OpenSearch Serverless']
    formatted_labels = [keyword_label(keyword) for keyword in keywords]

    get_background()
    apply_studio_style()

    main()


