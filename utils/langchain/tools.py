from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from langchain.pydantic_v1 import (
    BaseModel, 
    Field
)
from langchain.tools import StructuredTool

def tool_retriever_local(
        index_name:str,
        AZURE_SEARCH_ENDPOINT:str,
        AZURE_SEARCH_KEY:str,
        title_field: str="title",
        content_field: str="chunk",
        vector_field: str="chunk_vector", 
        semantic_search_inclusion: list[str]=["title", "chunk", "chunk_id"], 
        ) -> StructuredTool:
    
    # Retriever function (for tool)
    def retrieve_local(query: str):
        """Retrieve reference knowledge and facts from the database to respond to the user."""
        credential=AzureKeyCredential(AZURE_SEARCH_KEY)

        search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT,
                    index_name=index_name,
                    credential=credential)
        
        vector_query = VectorizableTextQuery(
            text=query, 
            k_nearest_neighbors=5, 
            fields=vector_field)

        documents = search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            query_type="semantic",
            select=semantic_search_inclusion,
            top=5
            )

        documents_dict = []
        for i, document in enumerate(documents):
            dict_output = {
                # "reference_id": document["chunk_id"],
                "reference_id": str(1+i),
                "title": document[title_field],
                "content": document[content_field],
            }
            documents_dict.append(dict_output)

        return documents_dict



    # tool_retriever_local input type
    class RetrieverLocalInput(BaseModel):
        query: str = Field(description="Query to search data from the database, considering sequence of chat (history).")



    # tool_retriever_local
    tool_retriever_local = StructuredTool.from_function(
        func = retrieve_local,
        name = "retrieve_local",
        description = "Retrieve reference knowledge and facts from the database to respond to the user.",
        args_schema=RetrieverLocalInput,
        return_direct = True
    )

    return tool_retriever_local