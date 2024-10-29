
from dotenv import load_dotenv
import os
from rest_framework.response import Response
from rest_framework.decorators import (
    api_view, 
    permission_classes
)
from utils.Azure_functions import (
    get_blob_list,
    get_blob_url,
    upload_blob,
    delete_blob,
    get_or_create_container,
    post_blob_metadata,
    get_blob_custom_metadata
)
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.documents import Document
from langchain_community.document_loaders import AzureBlobStorageContainerLoader
from langchain_text_splitters import CharacterTextSplitter
from rest_framework.permissions import IsAuthenticated
from utils.miscellaneous import (
    get_claim_from_token_http,
    scrape_url,
    generate_file_name_from_url
    )
from django.http import StreamingHttpResponse
from pprint import pprint
from backend.auth_azure import websocket_authenticated
from azure.search.documents.indexes import (
    SearchIndexClient,
    SearchIndexerClient
)
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    SemanticSearch,
    SearchIndexerDataSourceConnection,
    SearchIndexerSkillset,
    CognitiveServicesAccountKey,
    SearchIndexer,
    SearchIndexerDataSourceType,
    SplitSkill,
    OcrSkill,
    MergeSkill,
    AzureOpenAIEmbeddingSkill,
    SearchIndexerIndexProjection
)
from django.utils import timezone
from time import sleep
from datetime import datetime
from .models import KnowledgebaseStatus
from .serializers import KnowledgeBaseStatusSerializer
from rest_framework import viewsets

load_dotenv()
AZURE_SEARCH_ENDPOINT=os.getenv('AZURE_SEARCH_ENDPOINT')
AZURE_SEARCH_KEY=os.getenv('AZURE_SEARCH_KEY')
AZURE_STORAGE_ACCOUNT=os.getenv('AZURE_STORAGE_ACCOUNT')
AZURE_STORAGE_KEY=os.getenv('AZURE_STORAGE_KEY')
AZURE_OPENAI_ENDPOINT=os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY=os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_DEPLOYMENT_EMBEDDING=os.getenv('AZURE_OPENAI_DEPLOYMENT_EMBEDDING')



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload(request):
    # Retreive nature of request
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        container_name=case
        metadata={
            "tenant_id": case,
            "is_deleted": "false"
            }

    elif case == 'organisation':
        container_name=tenant_id
        metadata={
            "tenant_id": tenant_id,
            "is_deleted": "false"
            }

    # Get or create container
    get_or_create_container(container_name, AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY)

    # Upload file to Azure Blob Storage
    files=request.FILES
    for key in files.keys():
        file=files.get(key)
        upload_blob(data=file, output_name=file.name, container_name=container_name, account_name=AZURE_STORAGE_ACCOUNT, account_key=AZURE_STORAGE_KEY, metadata=metadata)
    return Response({"message": "Upload succeeded."}, status=200)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_blob_info(request):
    # Retreive nature of request
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        container_name=case
    elif case == 'organisation':
        container_name=tenant_id

    get_or_create_container(container_name, AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY)
    

    # Get the list of blobs in the container
    blob_metadatas=get_blob_list(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name)

    # Get url of the blobs
    for blob_metadata in blob_metadatas: # Let's change to async later
        blob_url=get_blob_url(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name, blob_metadata["name"])
        blob_metadata["url"]=blob_url

    return Response(blob_metadatas)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tag_delete_file(request):
    # Retreive variables
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        container_name=case
    elif case == 'organisation':
        container_name=tenant_id

    blob_names=request.data




    # Get custom metadata
    for blob_name in blob_names:
        current_metadata = get_blob_custom_metadata(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name, blob_name)
        print(current_metadata)

        # Update is_deleted flag
        new_metadata = current_metadata
        new_metadata["is_deleted"] = "true"
        post_blob_metadata(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name, blob_name, new_metadata)
    return Response({"message": "Soft deleton succeeded."})



# Create or run index & handle deletion (When it is called then finally delete the blob)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def create_or_run_index(request):
    # Start time to check if the indexer is running (down there)
    start_time = datetime.now()
    sleep(1)

    # Set names
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        container_name=case
        index_name=case
    elif case == 'organisation':
        container_name=tenant_id
        index_name=tenant_id

    vector_search_profile_name=f"{index_name}-vector-search"
    vector_search_argorithm_name=f"{index_name}-vector-search-argorithm"
    vector_search_vectoriser_name=f"{index_name}-vector-search-vectoriser"
    semantic_search_name=f"{index_name}-semantic-search"
    skillset_name=f"{index_name}-skillset"
    data_source_name=f"{index_name}"
    indexer_name=f"{index_name}"



    # Updat the knowledgebase_status 
    indexer_status, created =KnowledgebaseStatus.objects.get_or_create(
        indexer_name=indexer_name,
        defaults={
            'status': 'running',
            'last_updated': timezone.now()
        }
    )
    indexer_status.status='running'
    indexer_status.last_updated=timezone.now()
    indexer_status.save()



    # Set up client
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
    
    index_client=SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=credential
        )

    indexer_client=SearchIndexerClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=credential
        )



    # Try to run index
    try:
        start_time = datetime.now()
        indexer_client.run_indexer(indexer_name)

    # If there is no indexer to run, create one
    except: 
        # Index
        # Field
        fields=[
                SearchField(
                    name="chunk_id",
                    type=SearchFieldDataType.String,
                    key=True,
                    analyzer_name="keyword"
                ),
                SimpleField(
                    name="parent_id",
                    type=SearchFieldDataType.String,
                    filterable=True
                ),
                SearchableField(
                    name="chunk",
                    type=SearchFieldDataType.String
                ),
                SearchableField(
                    name="title",
                    type=SearchFieldDataType.String,
                ),
                SearchField(
                    name="tenant_id",
                    type=SearchFieldDataType.String,
                    filterable=True
                ),
                SimpleField(
                    name="user_id",
                    type=SearchFieldDataType.String,
                    filterable=True
                ),
                SearchField(
                    name="chunk_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=1536,
                    vector_search_profile_name=vector_search_profile_name,
                    hidden=False
                ),
            ]

        # Vector search configuration
        vector_search=VectorSearch(
            profiles=[
            {
                "name": vector_search_profile_name,
                "algorithm": vector_search_argorithm_name,
                "vectorizer": vector_search_vectoriser_name,
                "compression": None
            }
            ],
            algorithms=[
            {
                "name": vector_search_argorithm_name,
                "kind": "hnsw",
                "hnswParameters": {
                "metric": "cosine",
                "m": 4,
                "efConstruction": 400,
                "efSearch": 500
                },
                "exhaustiveKnnParameters": None
            }
            ],
            vectorizers=[
            {
                "name": vector_search_vectoriser_name,
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                "resourceUri": os.getenv("AZURE_OPENAI_ENDPOINT"),
                "deploymentId": "text-embedding-ada-002",
                "apiKey": os.getenv('AZURE_OPENAI_KEY'),
                "modelName": "text-embedding-ada-002",
                "authIdentity": None
                },
                "customWebApiParameters": None,
                "aiServicesVisionParameters": None,
                "amlParameters": None
            }
            ],
            compressions=[]
        )

        # Semantic search configuration
        semantic_search=SemanticSearch(
            default_configuration_name=semantic_search_name,
            configurations=[
            {
                "name": semantic_search_name,
                "prioritizedFields": {
                "titleField": {
                    "fieldName": "title"
                },
                "prioritizedContentFields": [
                    {
                    "fieldName": "chunk"
                    }
                ],
                "prioritizedKeywordsFields": []
                }
            }
            ]
        )

        # Create index
        index=SearchIndex(
            name=index_name,
            fields=fields, 
            vector_search=vector_search, 
            semantic_search=semantic_search)
        index_client.create_or_update_index(index)



        # Datasource
        data_source=SearchIndexerDataSourceConnection(
            name=data_source_name,
            type=SearchIndexerDataSourceType.AZURE_BLOB,
            connection_string= f"DefaultEndpointsProtocol=https;AccountName={AZURE_STORAGE_ACCOUNT};AccountKey={AZURE_STORAGE_KEY};EndpointSuffix=core.windows.net",
            container={"name": container_name},
            data_deletion_detection_policy={
                "@odata.type" :"#Microsoft.Azure.Search.SoftDeleteColumnDeletionDetectionPolicy",
                "softDeleteColumnName" : "is_deleted",
                "softDeleteMarkerValue" : "true"
            }
        )

        indexer_client.create_or_update_data_source_connection(data_source)



        # Skillset
        ocr_skill=OcrSkill(
            inputs=[{
                "name": "image",
                "source": "/document/normalized_images/*"
                }],
            outputs=[{
                "name": "text",
                "targetName": "text"
                }],
            name="#1",
            context="/document/normalized_images/*",
            should_detect_orientation=True
        )

        merge_skill=MergeSkill(
            inputs=[
                {
                "name": "text",
                "source": "/document/content"
                },
                {
                "name": "itemsToInsert",
                "source": "/document/normalized_images/*/text"
                },
                {
                "name": "offsets",
                "source": "/document/normalized_images/*/contentOffset"
                }
            ],
            outputs=[
                {
                "name": "mergedText",
                "targetName": "mergedText"
                }
            ],
            name="#2",
            context="/document"
        )

        split_skill=SplitSkill(
            inputs=[{
                "name": "text",
                "source": "/document/mergedText"
                }],
            outputs=[{
                "name": "textItems",
                "targetName": "pages"
                }],
            name="#3",
            context="/document",
            text_split_mode="pages",
            maximum_page_length=500,
            page_overlap_length=125,
            maximum_pages_to_take=0
        )

        embbedding_skill=AzureOpenAIEmbeddingSkill(
            inputs=[{
                "name": "text",
                "source": "/document/pages/*"
            }],
            outputs=[{
                "name": "embedding",
                "targetName": "text_vector"
            }],
            name="#4",
            context="/document/pages/*",
            resource_url=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            deployment_name=AZURE_OPENAI_DEPLOYMENT_EMBEDDING,
            model_name=AZURE_OPENAI_DEPLOYMENT_EMBEDDING,
            dimensions=1536
        )

        skillset=SearchIndexerSkillset(
            name=skillset_name,
            skills=[
                ocr_skill,
                merge_skill,
                split_skill,
                embbedding_skill
            ],
            cognitive_services_account=CognitiveServicesAccountKey(
                key=os.getenv("COGNITIVE_SERVICE_KEY")
            ),
            index_projection=SearchIndexerIndexProjection(
                selectors=[{
                    "targetIndexName": index_name,
                    "parentKeyFieldName": "parent_id",
                    "sourceContext": "/document/pages/*",
                    "mappings": [
                        {
                            "name": "chunk_vector",
                            "source": "/document/pages/*/text_vector",
                            "sourceContext": None,
                            "inputs": []
                        },
                        {
                            "name": "chunk",
                            "source": "/document/pages/*",
                            "sourceContext": None,
                            "inputs": []
                        },
                        {
                            "name": "title",
                            "source": "/document/metadata_storage_name",
                            "sourceContext": None,
                            "inputs": []
                        },
                        # {
                        #     "name": "user_id",
                        #     "source": "/document/user_id",
                        #     "sourceContext": None,
                        #     "inputs": []
                        # },
                        {
                            "name": "tenant_id",
                            "source": "/document/tenant_id",
                            "sourceContext": None,
                            "inputs": []
                        }
                    ]
                }],
                parameters={"projectionMode": "skipIndexingParentDocuments"}
            )
        )

        indexer_client.create_or_update_skillset(skillset)



        # Indexer
        indexer=SearchIndexer(
            name=indexer_name,
            data_source_name=data_source_name,
            target_index_name=index_name,
            skillset_name=skillset_name,
            parameters={
                "batchSize": None,
                "maxFailedItems": None,
                "maxFailedItemsPerBatch": None,
                "base64EncodeKeys": None,
                "configuration": {
                    "dataToExtract": "contentAndMetadata",
                    "parsingMode": "default",
                    "imageAction": "generateNormalizedImages"
                }
            }
        )

        indexer_client.create_or_update_indexer(indexer)
    


    # Track indexer status

    while True:
        status = indexer_client.get_indexer_status(name=indexer_name).as_dict()
        last_result = status.get('last_result')

        if last_result:
            last_result_status = last_result.get('status')
            last_result_start_time = datetime.strptime(last_result.get('start_time'), '%Y-%m-%dT%H:%M:%S.%fZ')
            print(last_result_status)
            print(last_result_start_time)
            print(start_time)
            print(last_result_start_time > start_time)
            if (last_result_status == 'success' and last_result_start_time > start_time):
                break
        sleep(10)
    


    # Updat the knowledgebase_status 
    indexer_status, created =KnowledgebaseStatus.objects.get_or_create(
        indexer_name=indexer_name,
        defaults={
            'status': 'completed',
            'last_updated': timezone.now()
        }
    )
    indexer_status.status='completed'
    indexer_status.last_updated=timezone.now()
    indexer_status.save()

    

    # Delete soft-deleted blobs 
    # get soft-deleted blobs
    all_blobs = get_blob_list(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name)
    soft_deleted_blobs = [blob for blob in all_blobs if blob["metadata"]["is_deleted"] == "true"]

    for blob in soft_deleted_blobs:
        delete_blob(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, container_name, blob["name"])

    return Response({"message":"Index created successfully."})



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_index_status(request):
    # Set names
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        indexer_name=case
    elif case == 'organisation':
        indexer_name=tenant_id



    # Set up client
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)

    indexer_client=SearchIndexerClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=credential
        )
    
    status = indexer_client.get_indexer_status(name=indexer_name)  # Call your SDK
    pprint(status.as_dict().get('lastResult')["end_time"])
    
    return Response({"status": status.as_dict()})




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scrape_urls(request):
    # Set names
    case=request.headers.get('Case')
    tenant_id=get_claim_from_token_http(request, 'tid')

    if case == 'customerservice':
        container_name=case
    elif case == 'organisation':
        container_name=tenant_id

    urls=request.data["urls"]
    
    # Generate blob name
    for url in urls:
        print(url)
        blob_name = generate_file_name_from_url(url)

        # Scrape the URL
        metadata={
            "tenant_id": tenant_id,
            "is_deleted": "false",
            "source": "web"
        }
        content=scrape_url(url)
        upload_blob(data=content, output_name=blob_name, container_name=container_name, account_name=AZURE_STORAGE_ACCOUNT, account_key=AZURE_STORAGE_KEY, metadata=metadata)
        print("finished")

    return Response({"message": "Success" })



class KnowledgeBaseStatusViewSet(viewsets.ModelViewSet):
    queryset = KnowledgebaseStatus.objects.all()
    serializer_class = KnowledgeBaseStatusSerializer

    def get_queryset(self):
        case = self.request.headers.get('Case')
        tenant_id = get_claim_from_token_http(self.request, 'tid')

        # Determine container and index names based on the case
        if case == 'customerservice':
            indexer_name = case
        elif case == 'organisation':
            indexer_name = tenant_id



        # Create knowledge base status
        KnowledgebaseStatus.objects.get_or_create(indexer_name=indexer_name)



        # Filter queryset based on indexer_name
        queryset = super().get_queryset().filter(indexer_name=indexer_name)

        return queryset


