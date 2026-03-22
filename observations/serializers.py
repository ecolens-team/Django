from rest_framework import serializers
from .models import Observation, Species, Image

class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = '__all__'

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ['id', 'image', 'image_quality', 'date']

class ObservationSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True) 

    class Meta:
        model = Observation
        fields = [
            'id', 'user', 'species', 'timestamp', 'longitude', 
            'latitude', 'description', 'confidence_level', 'verified', 'images'
        ]
        read_only_fields = ['user', 'confidence_level', 'verified']