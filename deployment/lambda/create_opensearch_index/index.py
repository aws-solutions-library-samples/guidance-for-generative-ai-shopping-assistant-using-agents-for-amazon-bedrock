import boto3
import os
import logging
from typing import Sequence, TypedDict
from urllib.parse import urlparse
import time
from opensearchpy import (
    AWSV4SignerAuth,
    OpenSearch,
    RequestsHttpConnection,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class MetadataManagementField(TypedDict):
    MappingField: str
    DataType: str
    Filterable: bool

def connect_opensearch(endpoint: str) -> OpenSearch:
    service = "aoss" if "aoss" in endpoint else "es"
    logger.info(f"Connecting to OpenSearch service: {service} at {endpoint}")
    return OpenSearch(
        hosts=[
            {
                "host": endpoint,
                "port": 443,
            }
        ],
        http_auth=AWSV4SignerAuth(
            boto3.Session().get_credentials(), os.getenv("AWS_REGION"), service
        ),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=10,
    )

def create_mapping(
    vector_field: str,
    dimensions: int,
    metadata_management: Sequence[MetadataManagementField],
) -> dict:
    mapping = {
        "properties": {
            vector_field: {
                "type": "knn_vector",
                "dimension": dimensions,
                "method": {
                    "engine": "faiss",
                    "space_type": "l2",
                    "name": "hnsw",
                    "parameters": {
                    }
                },
            },
            "id": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
        },
    }
    for field in metadata_management:
        mapping["properties"][field["MappingField"]] = {
            "type": field["DataType"],
            "index": "true" if field["Filterable"] else "false",
        }
    return mapping

def create_setting() -> dict:
    setting = {
        "index": {
            "number_of_shards": "2",
            "knn.algo_param": {"ef_search": "512"},
            "knn": "true",
        },
    }
    return setting

def create_or_update_index(
    client: OpenSearch, index_name: str, mapping: dict[str, str],  setting: dict[str, str]
) -> None:
    
    logger.info(f"setting: {setting}")
    logger.info(f"mapping: {mapping}")
    if client.indices.exists(index_name):
        logger.info(f"Index {index_name} already exists. Updating mapping.")
        client.indices.put_mapping(
            index=index_name,
            body=mapping
        )
        client.indices.put_settings(
            index=index_name,
            body=setting
        )
    else:
        logger.info(f"Creating index {index_name}")

        client.indices.create(
            index_name,
            body={
                "settings": setting,
                "mappings": mapping,
            },
            params={"wait_for_active_shards": "all"},
        )
    
    logger.debug(f"Sleep for 30 seconds for Bedrock KB {index_name}")
    time.sleep(30)

def handler(event, context):
    index_name = os.environ['INDEX_NAME']
    aoss_endpoint = os.environ['AOSS_ENDPOINT']
    vector_field = os.environ['VECTOR_FIELD']
    dimensions = os.environ['VECTOR_DIMENSION']
    text_field = os.environ['TEXT_FIELD']
    metadata_field = os.environ['METADATA_FIELD'] 

    aoss_endpoint_name  = ''

    parsed_url  = urlparse(aoss_endpoint)
    if not parsed_url .scheme or not parsed_url .netloc:
        raise ValueError(f"Invalid OpenSearch endpoint format: {aoss_endpoint}")
    
    aoss_endpoint_name = parsed_url.netloc

    # Amazon Bedrock Default mapping
    metadata_management = [
        MetadataManagementField(
            MappingField= text_field,
            DataType = 'text',
            Filterable = True,
        ),
        MetadataManagementField(
            MappingField= metadata_field,
            DataType = 'text',
            Filterable = False,
        ),
    ]

    try:
        client = connect_opensearch(aoss_endpoint_name)
        mapping = create_mapping(vector_field, dimensions, metadata_management)
        setting = create_setting()

        create_or_update_index(client, index_name, mapping, setting)

    except Exception as e:
        logger.error(f"Error creating or updating index {index_name}")
        logger.exception(e)
        raise e
    return index_name
