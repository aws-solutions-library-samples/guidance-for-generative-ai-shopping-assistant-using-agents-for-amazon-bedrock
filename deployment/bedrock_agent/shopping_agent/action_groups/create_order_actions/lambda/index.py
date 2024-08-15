import json
import urllib.request
import os
import uuid
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
parameters_http_port = 2773

def get_ssm_parameter(param_name):
    try:
        # Encode the parameter name
        encoded_param_name = urllib.parse.quote(param_name)

        # Retrieve parameter from Parameter Store using extension cache
        req = urllib.request.Request(f'http://localhost:2773/systemsmanager/parameters/get?name={encoded_param_name}')
        req.add_header('X-Aws-Parameters-Secrets-Token', aws_session_token)
        response = urllib.request.urlopen(req)
        config = response.read()

        return json.loads(config)['Parameter']['Value']
    except urllib.error.HTTPError as e:
        if e.code == 404:  # Parameter not found
            logger.error(f"Parameter {param_name} not found. Returning empty value.")
            return ""
        else:
            logger.error(f"An error occurred while retrieving parameter {param_name}: {e}")
            return ""
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return ""

def get_secret(secret_name):
    try:
        # Encode the parameter name
        encoded_param_name = urllib.parse.quote(secret_name)

        # Retrieve parameter from Parameter Store using extension cache
        req = urllib.request.Request(f'http://localhost:2773/systemsmanager/secretsmanager/get?secretId={encoded_param_name}')
        req.add_header('X-Aws-Parameters-Secrets-Token', aws_session_token)
        response = urllib.request.urlopen(req)
        secret = response.read()

        return json.loads(secret)["SecretString"]
    except urllib.error.HTTPError as e:
        if e.code == 404:  # Parameter not found
            logger.error(f"Secret {secret_name} not found. Returning empty value.")
            return ""
        else:
            logger.error(f"An error occurred while retrieving Secret {secret_name}: {e}")
            return ""
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return ""

def handler(event, context):
    logging.info(event)
    action = event['actionGroup']
    api_path = event['apiPath']
    http_method = event['httpMethod']
    
    # Get API Gateway params from environment variable or SSM Parameter Store
    apigateway_url =  os.environ.get('API_URL', get_ssm_parameter(os.environ.get('API_URL_PARAM')))
    api_key =  os.environ.get('API_URL', get_secret(os.environ.get('API_KEY_SECRET_NAME')))

    if api_path == "/orders" and http_method == "POST":
        body = create_order(event)
    elif api_path == "/products/{productId}/inventory" and http_method == "GET":
        body = get_product_inventory(event, apigateway_url, api_key)
    elif api_path == "/orders/{orderId}/sendEmail" and http_method == "POST":
        body = send_order_confirmation_email(event)
    else:
        body = {"{}::{} is not a valid api, try another one.".format(action, api_path)}

    response_body = {
        'application/json': {
            'body': str(body)
        }
    }
    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }

    response = {'response': action_response}
    return response

def get_named_parameter(event, name):
    return next(item for item in event['parameters'] if item['name'] == name)['value']

def get_named_property(event, name):
    return next(
        item for item in
        event['requestBody']['content']['application/json']['properties']
        if item['name'] == name)['value']

def invoke_url(url, path, api_key, method='GET', data=None):
    url = url + path
    headers = {
    'Content-Type': 'application/json',
    'x-api-key': api_key
    }

    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())

def get_product_inventory(event, apigateway_url, api_key):
    return invoke_url(apigateway_url, 'products/id/' + get_named_parameter(event, 'productId'), api_key)

def create_order(event):
    email = get_named_property(event,"email")
    order_items_str = get_named_property(event,"orderItems")
    first_name = get_named_property(event,"firstName")
    last_name = get_named_property(event,"lastName")
    address = get_named_property(event,"address")
    city =get_named_property(event,"city")
    zip_code = get_named_property(event,"zipCode")
    state = get_named_property(event,"state")
    country = get_named_property(event,"country")
    
    try:
        order_items = json.loads(order_items_str)
    except (json.JSONDecodeError, KeyError, TypeError):
        # Handle the case where order_details is not a valid JSON string or doesn't have the expected structure
        return {"error": "Invalid order details format"}

    # Generate a random GUID as a prefix for the order ID
    order_id_prefix = str(uuid.uuid4())

    # Implement order creation logic here
    order_id = f"{order_id_prefix}-ORDER"
    total_amount = sum(item["price"] * item["quantity"] for item in order_items)

    order_response = {
        "id": order_id,
        "email": email,
        "order": {
            "orderItems": order_items,
            "shippingAddress": {
                "firstName": first_name,
                "lastName": last_name,
                "address": address,
                "city": city,
                "zipCode": zip_code,
                "state": state,
                "country": country
            }
        },
        "totalAmount": total_amount
    }

    response = {
        "orderId": order_id,
        "orderDetails": order_response
    }

    response = {
        "orderId": order_id,
        "orderDetails": order_response
    }

    return response

def send_order_confirmation_email(event):
    email = get_named_property(event,"email")
    email_body = get_named_property(event,"emailBody")
    order_id = get_named_parameter(event,"orderId")

    # Validate required fields
    if not all([email, email_body, order_id]):
        raise ValueError("Missing required fields in the request body")

   
    return f"Email sent successfully to {email}"
