from django.db import models

# Create your models here.
class ChatHistory(models.Model):
    user_uuid = models.CharField(max_length=50, null=True)
    datetime = models.DateTimeField(auto_now_add=True)
    messages = models.JSONField(null=True)

    class Meta:
        db_table = 'chat_history'



# class ChatHistoryClient(models.Model):
#     user_uuid = models.CharField(max_length=50, null=True)
#     username = models.CharField(max_length=50, null=True)
#     datetime = models.DateTimeField(auto_now_add=True)
#     log = models.CharField(max_length=5000, null=True)
#     summary = models.CharField(max_length=5000, null=True)
#     priority = models.CharField(max_length=50, null=True)

#     class Meta:
#         db_table = 'chat_history_client'