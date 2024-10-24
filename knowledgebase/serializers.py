from rest_framework import serializers
from .models import KnowledgebaseStatus

class KnowledgeBaseStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgebaseStatus
        fields = '__all__'

