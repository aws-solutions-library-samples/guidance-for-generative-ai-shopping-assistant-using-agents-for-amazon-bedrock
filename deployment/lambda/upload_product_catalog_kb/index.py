import json
import os
import boto3

s3 = boto3.client('s3')

def handler(event, context):
    source_bucket = os.environ['DESTINATION_BUCKET']
    cloudfront_url = os.environ['CLOUDFRONT_URL']
    app_url = os.environ['APP_URL']
    bucket_prefix = os.environ['BUCKET_PREFIX']

    # Read products.json
    response = s3.get_object(Bucket=source_bucket, Key=f'products.json')
    products = json.loads(response['Body'].read().decode('utf-8'))

    for product in products:
        # Create product text file
        product_text = f"""id: {product['id']}
            name: {product['name']}
            description: {product['description']}
            category: {product['category']}
            style: {product['style']}
            aliases: {product['aliases']}
            price: {product['price']}
            promoted: {product['promoted']}
            featured: {product['featured']}
            gender_affinity: {product['gender_affinity']}
            image: {cloudfront_url}/images/{product['image']}
            url: {app_url}/#/product/{product['id']}
            """
        s3.put_object(
            Bucket=source_bucket,
            Key=f"{bucket_prefix}/{product['id']}.txt",
            Body=product_text
        )

        # Create metadata file
        metadata = {
            "metadataAttributes": {
                "category": product['category'],
                "style": product['style'],
                "price": str(product['price']),
                "promoted": product['promoted'],
                "featured": product['featured']
            }
        }
        s3.put_object(
            Bucket=source_bucket,
            Key=f"{bucket_prefix}/{product['id']}.txt.metadata.json",
            Body=json.dumps(metadata)
        )

    return {
        'statusCode': 200,
        'body': json.dumps('Product catalog processed successfully')
    }
