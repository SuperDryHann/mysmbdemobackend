# Install necessary packages
# pip install azure-search-documents
from dotenv import load_dotenv
import os
from azure.core.credentials import AzureKeyCredential
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
load_dotenv()
AZURE_SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT')
AZURE_SEARCH_KEY = os.getenv('AZURE_SEARCH_KEY')
AZURE_STORAGE_ACCOUNT = os.getenv('AZURE_STORAGE_ACCOUNT')
AZURE_STORAGE_KEY = os.getenv('AZURE_STORAGE_KEY')
AZURE_OPENAI_ENDPOINT=os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY=os.getenv('AZURE_OPENAI_KEY')
AZURE_OPENAI_DEPLOYMENT_EMBEDDING=os.getenv('AZURE_OPENAI_DEPLOYMENT_EMBEDDING')



# Set names
index_name="yoyoyoyo"
blob_container_name="yoyoyoyo"
vector_search_profile_name = f"{index_name}-vector-search"
vector_search_argorithm_name = f"{index_name}-vector-search-argorithm"
vector_search_vectoriser_name = f"{index_name}-vector-search-vectoriser"
semantic_search_name = f"{index_name}-semantic-search"
skillset_name = f"{index_name}-skillset"
data_source_name = f"{index_name}"
indexer_name = f"{index_name}"

# Set up client
credential = AzureKeyCredential(AZURE_SEARCH_KEY)
index_client = SearchIndexClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    credential=credential
    )

indexer_client = SearchIndexerClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    credential=credential
    )



# Index
# Field
fields = [
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
vector_search = VectorSearch(
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
semantic_search = SemanticSearch(
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
index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search, semantic_search = semantic_search)
index_client.create_or_update_index(index)



# Datasource
data_source = SearchIndexerDataSourceConnection(
    name=data_source_name,
    type=SearchIndexerDataSourceType.AZURE_BLOB,
    connection_string= f"DefaultEndpointsProtocol=https;AccountName={AZURE_STORAGE_ACCOUNT};AccountKey={AZURE_STORAGE_KEY};EndpointSuffix=core.windows.net",
    container={"name": "yoyo"}
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

split_skill = SplitSkill(
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
    maximum_page_length=2000,
    page_overlap_length=500,
    maximum_pages_to_take=0
)

embbedding_skill = AzureOpenAIEmbeddingSkill(
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

skillset = SearchIndexerSkillset(
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
                # {
                #     "name": "tenant_id",
                #     "source": "/document/tenant_id",
                #     "sourceContext": None,
                #     "inputs": []
                # }
            ]
        }],
        parameters={"projectionMode": "skipIndexingParentDocuments"}
    )
)

indexer_client.create_or_update_skillset(skillset)



# Indexer
indexer = SearchIndexer(
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
indexer_client.run_indexer(indexer_name)
from pprint import pprint
pprint(indexer_client.get_indexer_status(name=indexer_name).as_dict()["last_result"]["status"], indexer_client.get_indexer_status(name=indexer_name).as_dict()["last_result"]["start_time"], indexer_client.get_indexer_status(name=indexer_name).as_dict()["last_result"]["end_time"])



print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
