import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CLOUDFRONT_URL = os.environ['CLOUDFRONT_URL']

# Load the products data
with open('data/products.json') as f:
    PRODUCTS = json.load(f)


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

def get_product_by_id(product_id):
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    if product:
        product['image'] = f"{CLOUDFRONT_URL}/{product['image']}"
        # product['url'] = f"{APP_URL}/products/{product['id']}"
        return create_response(200, product)
    else:
        return create_response(404, {'message': 'Product not found'})

def get_featured_products():
    featured_products = [p for p in PRODUCTS if p.get('featured', True)]
    for product in featured_products:
        product['image'] = f"{CLOUDFRONT_URL}/{product['image']}"
        # product['url'] = f"{APP_URL}/products/{product['id']}"
    return create_response(200, featured_products)

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    path = event['resource']
    http_method = event['httpMethod']

    if http_method == 'OPTIONS':
        return create_response(200, {})

    if path == '/products/id/{productId}' and http_method == 'GET':
        product_id = event['pathParameters']['productId']
        return get_product_by_id(product_id)
    elif path == '/products/featured' and http_method == 'GET':
        return get_featured_products()
    else:
        return create_response(404, {'message': 'Resource Not Found'})
