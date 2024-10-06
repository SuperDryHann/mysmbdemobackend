from django.shortcuts import render
from utils.Azure_functions import get_blob_list, get_blob_url, upload_blob, delete_blob
from dotenv import load_dotenv
import os
from rest_framework.response import Response
from rest_framework.decorators import api_view
from azure.search.documents.indexes.models import ScoringProfile, SearchableField, SearchField, SearchFieldDataType, SimpleField, TextWeights
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.documents import Document
from langchain_community.document_loaders import AzureBlobStorageContainerLoader
from langchain_text_splitters import CharacterTextSplitter
load_dotenv()

@api_view(['POST'])
def upload(request):
    AZURE_STORAGE_ACCOUNT=os.getenv('AZURE_STORAGE_ACCOUNT')
    AZURE_STORAGE_KEY=os.getenv('AZURE_STORAGE_KEY')
    AZURE_STORAGE_CONTAINER=os.getenv('AZURE_STORAGE_CONTAINER')

    try:
        # Upload file to Azure Blob Storage
        files = request.FILES
        for key in files.keys():
            file = files.get(key)
            upload_blob(data = file, output_name = file.name, container_name = AZURE_STORAGE_CONTAINER, account_name = AZURE_STORAGE_ACCOUNT, account_key = AZURE_STORAGE_KEY)
        return Response({"message": "Upload succeeded."}, status = 200)

    except Exception as e:
        print(e)
        return Response({"error": str(e)}, status = 500)



@api_view(['GET'])
def get_blob_info(request):
    AZURE_STORAGE_ACCOUNT=os.getenv('AZURE_STORAGE_ACCOUNT')
    AZURE_STORAGE_KEY=os.getenv('AZURE_STORAGE_KEY')
    AZURE_STORAGE_CONTAINER=os.getenv('AZURE_STORAGE_CONTAINER')

    # Get the list of blobs in the container
    blob_metadatas = get_blob_list(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, AZURE_STORAGE_CONTAINER)

    # Get url of the blobs
    for blob_metadata in blob_metadatas: # Let's change to async later
        blob_url = get_blob_url(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, AZURE_STORAGE_CONTAINER, blob_metadata["name"])
        blob_metadata["url"] = blob_url

    return Response(blob_metadatas)



@api_view(['POST'])
def delete_file(request):
    AZURE_STORAGE_ACCOUNT=os.getenv('AZURE_STORAGE_ACCOUNT')
    AZURE_STORAGE_KEY=os.getenv('AZURE_STORAGE_KEY')
    AZURE_STORAGE_CONTAINER=os.getenv('AZURE_STORAGE_CONTAINER')
    blob_name = request.data["name"] 

    # Get the list of blobs in the container
    delete_blob(AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, AZURE_STORAGE_CONTAINER, blob_name)
    return Response({"message": "The deleted successfully."})

 

@api_view(['GET'])
def create_index(request):
    AZURE_STORAGE_ACCOUNT=os.getenv('AZURE_STORAGE_ACCOUNT')
    AZURE_STORAGE_KEY=os.getenv('AZURE_STORAGE_KEY')
    AZURE_STORAGE_CONTAINER=os.getenv('AZURE_STORAGE_CONTAINER')
    AZURE_SEARCH_ENDPOINT=os.getenv('AZURE_SEARCH_ENDPOINT')
    AZURE_SEARCH_KEY=os.getenv('AZURE_SEARCH_KEY')
    AZURE_OPENAI_DEPLOYMENT_EMBEDDING=os.getenv('AZURE_OPENAI_DEPLOYMENT_EMBEDDING')
    AZURE_OPENAI_API_VERSION=os.getenv('AZURE_OPENAI_API_VERSION')
    AZURE_OPENAI_ENDPOINT=os.getenv('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_KEY=os.getenv('AZURE_OPENAI_KEY')

    index_name="unsw" ###################
    credential = AzureKeyCredential(AZURE_SEARCH_KEY)
    with SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=credential) as search_client:
        search_client.delete_index(index_name)

    # Azure AI search retriever
    embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
        azure_deployment = AZURE_OPENAI_DEPLOYMENT_EMBEDDING,
        openai_api_version = AZURE_OPENAI_API_VERSION,
        azure_endpoint = AZURE_OPENAI_ENDPOINT,
        api_key = AZURE_OPENAI_KEY,
    )
    embedding_function = embeddings.embed_query

    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=len(embedding_function("Text")),
            vector_search_profile_name="myHnswProfile",
        ),
        SearchableField(
            name="metadata",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        # Additional field to store the title
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        # Additional field for filtering on document source
        SimpleField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        #     SimpleField(
        #     name="filter_council",
        #     type=SearchFieldDataType.String,
        #     filterable=True,
        # ),
    ]

    index_name: str = index_name
    vector_store: AzureSearch = AzureSearch(
        azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
        azure_search_key=AZURE_SEARCH_KEY,
        index_name=index_name,
        embedding_function=embedding_function,
        fields=fields
    )

    ## load documents
    ### load document from blob using default method
    loader = AzureBlobStorageContainerLoader(
        conn_str=f"DefaultEndpointsProtocol=https;AccountName={AZURE_STORAGE_ACCOUNT};AccountKey={AZURE_STORAGE_KEY};EndpointSuffix=core.windows.net",
        container=AZURE_STORAGE_CONTAINER
    )
    raw_documents = loader.load()

    ### Modify document to include metadata (filters)
    documents = []
    for document in raw_documents:
        document.page_content
        source = document.metadata.get("source")
        title = source.split("/")[-1] # Extract title from source.
        # filter_council = source.split("/")[-2] # Extract filter_council from source. Blob's directory must be a name of council.
        # metadata = {"title" : title, "source" : source, "filter_concil" : filter_council}
        metadata = {"title" : title, "source" : source}
        documents.append(Document(page_content = document.page_content, metadata = metadata))

    ## Chunk documents
    chunk_size = 500
    text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_size * 0.5)
    chunk = text_splitter.split_documents(documents)

    ## Create retriever
    vector_store.add_documents(documents=chunk)

    return Response({"message":"Index created successfully."})