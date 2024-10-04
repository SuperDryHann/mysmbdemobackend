# from django.db import models
# from pgvector.django import VectorField

# class ChatHistoryClient(models.Model):
#     tenant_id = models.CharField(max_length=50, null=True)
#     role_id = models.CharField(max_length=50, null=True)
#     user_id = models.CharField(max_length=50, null=True)
#     project_id = models.CharField(max_length=50, null=True)
#     content = models.DateTimeField(auto_now_add=True)
#     content_vector = VectorField(null=True)
#     metadata = models.CharField(max_length=3000, null=True)
#     title = models.CharField(max_length=3000, null=True)
#     source = models.CharField(max_length=3000, null=True)
#     class Meta:
#         db_table = 'knowledgebase'