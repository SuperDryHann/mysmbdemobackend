from django.db import models

class KnowledgebaseStatus(models.Model):
    indexer_name = models.CharField(max_length=50, null=True)
    status= models.CharField(max_length=50, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'knowledgebase_status'