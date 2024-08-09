import boto3
import os
import tarfile
import logging
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    s3 = boto3.client('s3')
    bucket_name = os.environ['BUCKET_NAME']
    images_url = os.environ['IMAGES_URL']

    try:
        # Download the tar.gz file to /tmp
        logger.info(f"Downloading images from {images_url}")
        filename, _ = urllib.request.urlretrieve(images_url, '/tmp/images.tar.gz')
        logger.info(f"Filename: {filename}")
        
        # Extract files to /tmp directory
        extract_path = '/tmp/extracted_images'
        os.makedirs(extract_path, exist_ok=True)
        
        logger.info("Extracting files")
        with tarfile.open('/tmp/images.tar.gz') as tar:
            tar.extractall(path=extract_path)
        
        os.remove('/tmp/images.tar.gz')

        # Upload image files to S3
        logger.info("Uploading files to S3")
        for root, _, files in os.walk(extract_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                s3_key = f"images/{file_name}"
                with open(file_path, 'rb') as file_data:
                    s3.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=file_data
                    )
                    # logger.info(f"Uploaded {s3_key}")

        return {
            'statusCode': 200,
            'body': 'Images uploaded successfully'
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error uploading images: {str(e)}'
        }
