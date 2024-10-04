from django.urls import path

from . import views

app_name = "knowledgebase"
urlpatterns = [
    path('upload/', views.upload, name = "upload"),
    path('get_blob_info/', views.get_blob_info, name = "get_blob_info"),
    path('create_index/', views.create_index, name = "create_index"),
    path('delete_file/', views.delete_file, name = "delete_file"),
]