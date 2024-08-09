import json
import os
import boto3
import logging
import urllib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
bedrock_agent = boto3.client('bedrock-agent')
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

def upload_product_files(source_bucket, cloudfront_url, app_url, bucket_prefix, products):
    logger.info(f"Starting to upload product files to bucket: {source_bucket}")
    for product in products:
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
url: {app_url}/product/?product_id={product['id']}
"""
        s3.put_object(
            Bucket=source_bucket,
            Key=f"{bucket_prefix}/{product['id']}.txt",
            Body=product_text
        )
        logger.debug(f"Uploaded product text file for product ID: {product['id']}")

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
        logger.debug(f"Uploaded metadata file for product ID: {product['id']}")
    
    logger.info("Finished uploading all product files")
    return {"message": "All product files uploaded successfully"}

def start_knowledge_base_ingestion(knowledge_base_id, data_source_id):
    if not knowledge_base_id or not data_source_id:
        logger.warning("Knowledge base ID or data source ID is missing. Skipping ingestion job.")
        return {"message": "Ingestion job not started due to missing IDs"}

    logger.info(f"Starting ingestion job for knowledge base ID: {knowledge_base_id} and data source ID: {data_source_id}")
    response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id
    )

    ingestion_job = response.get('ingestionJob', {})
        
    logger.info(f"Ingestion job started successfully. Job ID: {ingestion_job.get('ingestionJobId', 'N/A')}, Job Status: {ingestion_job.get('status', 'N/A')}")
    return {"message": "Ingestion job started successfully", "jobId": ingestion_job.get('ingestionJobId', 'N/A')}

def handler(event, context):
    source_bucket = os.environ['BUCKET_NAME']
    bucket_prefix = os.environ['BUCKET_PREFIX']
    knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
    data_source_id = os.environ.get('DATA_SOURCE_ID')
    cloudfront_url = get_ssm_parameter(os.environ['CLOUDFRONT_URL_PARAM'])
    app_url = get_ssm_parameter(os.environ['APP_URL_PARAM'])

    logger.info(f"Handler started with bucket: {source_bucket}, prefix: {bucket_prefix}")

    try:
        response = s3.get_object(Bucket=source_bucket, Key='products.json')
        products = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"Successfully read products.json. Found {len(products)} products.")

        upload_result = upload_product_files(source_bucket, cloudfront_url, app_url, bucket_prefix, products)
        
        ingestion_result = start_knowledge_base_ingestion(knowledge_base_id, data_source_id)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'upload_result': upload_result,
                'ingestion_result': ingestion_result
            })
        }
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
