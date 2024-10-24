from django.urls import path

from . import views

app_name = "knowledgebase"
urlpatterns = [
    path('upload/', views.upload, name = "upload"),
    path('get_blob_info/', views.get_blob_info, name = "get_blob_info"),
    path('create_or_run_index/', views.create_or_run_index, name = "create_or_run_index"),
    path('tag_delete_file/', views.tag_delete_file, name = "tag_delete_file"),
    path('get_index_status/', views.get_index_status, name = "get_index_status"),
    path('scrape_urls/', views.scrape_urls, name = "scrape_urls"),
    path('get_knowledge_base_status/', views.KnowledgeBaseStatusViewSet.as_view({'get': 'list'}), name='get_knowledge_base_status'),
]