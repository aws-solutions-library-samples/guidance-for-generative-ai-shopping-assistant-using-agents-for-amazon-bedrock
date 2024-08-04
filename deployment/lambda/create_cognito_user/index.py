import boto3
import os
from botocore.exceptions import ClientError

def handler(event, context):
    cognito = boto3.client('cognito-idp')
    user_pool_id = os.environ['USER_POOL_ID']
    default_user_email = os.environ['DEFAULT_USER_EMAIL']
    default_user_name = os.environ['DEFAULT_USER_NAME']
    default_temp_password = os.environ['DEFAULT_TEMP_PASSWORD']

    try:
        # Check if the user already exists
        try:
            cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=default_user_name
            )
            print(f"User {default_user_name} already exists. Skipping creation.")
            return {
                'statusCode': 200,
                'body': f'User {default_user_name} already exists'
            }
        except cognito.exceptions.UserNotFoundException:
            # User doesn't exist, proceed with creation
            cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=default_user_name,
                UserAttributes=[
                    {'Name': 'email', 'Value': default_user_email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=default_temp_password,
                MessageAction='SUPPRESS',
                ForceAliasCreation=False
            )

            print(f"User {default_user_name} created successfully and will be forced to change password on first login")
            return {
                'statusCode': 200,
                'body': f'User {default_user_name} created successfully and will be forced to change password on first login'
            }

    except Exception as e:
        print(f"Error handling user: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error handling user: {str(e)}'
        }
