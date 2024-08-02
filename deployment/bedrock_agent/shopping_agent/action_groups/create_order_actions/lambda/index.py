import json
import urllib.request
import os
import uuid

# Get the API Gateway URL from the environment variable
apigateway_url = os.environ.get('API_URL', '')

headers = {
    'Content-Type': 'application/json'
}

def lambda_handler(event, context):
    print(event)
    action = event['actionGroup']
    api_path = event['apiPath']
    http_method = event['httpMethod']

    if api_path == "/orders" and http_method == "POST":
        body = create_order(event)
    elif api_path == "/products/{productId}/inventory" and http_method == "GET":
        body = get_product_inventory(event)
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

def invoke_url(path, method='GET', data=None):
    url = apigateway_url + path
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())

def get_product_inventory(event):
    return invoke_url('products/id/' + get_named_parameter(event, 'productId'))

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
