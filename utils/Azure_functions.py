from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from datetime import datetime, timedelta
import time
import mimetypes



def get_blob_url(account_name, account_key, container_name, blob_name):
    blob_service_client = BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=account_key)
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)  # SAS URL will be valid for 1 hour
    )
    blob_url_with_sas = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    return blob_url_with_sas



def get_blob_list(account_name, account_key, container_name, folder_name=None):
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_list = container_client.list_blobs(name_starts_with=folder_name)

    blobs_metadata = []
    for blob in blob_list:
        blob_client = container_client.get_blob_client(blob.name)
        blob_properties = blob_client.get_blob_properties()
        metadata = {
            "name": blob.name,
            "id": blob_properties.etag.replace('"', ''), # Remove double quotes
            "metadata": blob_properties.metadata
        }
        blobs_metadata.append(metadata)
    return blobs_metadata



def delete_blob(account_name, account_key, container_name, blob_name):
    # Create a blob service client
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    
    # Delete the blob
    blob_client.delete_blob()
    return f"Blob with name {blob_name} deleted successfully."



def delete_all_blobs(account_name, account_key, container_name):
    # Create a blob service client
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    # List all blobs in the container and delete each one
    blob_list = container_client.list_blobs()
    for blob in blob_list:
        container_client.delete_blob(blob.name)



def OCR(image_url, endpoint, subscription_key):
    # Instantiate the ComputerVisionClient
    computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

    # Call the read method
    read_response = computervision_client.read(image_url,  raw=True)

    # Get the operation location (URL with an ID at the end) from the response
    read_operation_location = read_response.headers["Operation-Location"]

    # Grab the ID from the URL
    operation_id = read_operation_location.split("/")[-1]

    # Call the "GET" API and wait for it to retrieve the results 
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    # Collect results, line by line
    lines = []
    if read_result.status == OperationStatusCodes.succeeded:
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                lines.append(line.text)

    # Join the lines into a single string and return it
    return ' '.join(lines)



def upload_blob(data, output_name, container_name, account_name, account_key):
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container_name, output_name)

    try: 
        content_type = data.content_type
    except:
        content_type = "application/octet-stream"

    blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type)
        )
