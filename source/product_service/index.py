import json
import os
import logging
import urllib
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
s3_bucket = os.environ['BUCKET_NAME']
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
        print('Cinfig', json.loads(config))
        return json.loads(config)['Parameter']['Value']
    except urllib.error.HTTPError as e:
        if e.code == 404:  # Parameter not found
            print(f"Parameter {param_name} not found. Returning empty value.")
            return ""
        else:
            print(f"An error occurred while retrieving parameter {param_name}: {e}")
            return ""
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return ""

def download_file_from_s3(bucket, key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        logger.error(f"Error downloading {key} from S3 bucket {bucket}: {e}")
        raise

def load_products():
    local_file_path = '/tmp/products.json'
    if not os.path.exists(local_file_path):
        products_data = download_file_from_s3(s3_bucket, key='products.json')
        with open(local_file_path, 'w') as f:
            json.dump(products_data, f)
    else:
        with open(local_file_path, 'r') as f:
            products_data = json.load(f)
    return products_data

def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',  # Allow all origins
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body)
    }

def get_product_by_id(product_id, app_url, image_url):
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    if product:
        product['image'] = f"{image_url}/{product['image']}"
        product['url'] = f"{app_url}/product/?product_id={product['id']}"
        return create_response(200, product)
    else:
        return create_response(404, {'message': 'Product not found'})

def get_featured_products(app_url, image_url):
    featured_products = [p for p in PRODUCTS if p.get('featured', True)]
    for product in featured_products:
        product['image'] = f"{image_url}/{product['image']}"
        product['url'] = f"{app_url}/product/?product_id={product['id']}"
    return create_response(200, featured_products)

PRODUCTS = load_products()

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    path = event['resource']
    http_method = event['httpMethod']

    if http_method == 'OPTIONS':
        return create_response(200, {})
    
    cloudfront_url = get_ssm_parameter(os.environ['CLOUDFRONT_URL_PARAM'])
    app_url = get_ssm_parameter(os.environ['APP_URL_PARAM'])
    image_url= f"{cloudfront_url}/images"

    if path == '/products/id/{productId}' and http_method == 'GET':
        product_id = event['pathParameters']['productId']
        return get_product_by_id(product_id, app_url, image_url)
    elif path == '/products/featured' and http_method == 'GET':
        return get_featured_products(app_url, image_url)
    else:
        return create_response(404, {'message': 'Resource Not Found'})
