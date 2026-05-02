from rest_framework import serializers
from observations.models import Observation, ObservationReport


class ObservationQueueSerializer(serializers.ModelSerializer):
    species_name = serializers.CharField(source='species.scientific_name', read_only=True)
    thumbnail = serializers.SerializerMethodField()
    observer = serializers.CharField(source='user.username', read_only=True)
    report_count = serializers.IntegerField(read_only=True)


    class Meta:
        model = Observation
        fields = ['id', 'species_name', 'thumbnail', 'confidence_level', 'report_count',
                'longitude', 'latitude', 'governorate', 'observer', 'verified', 'timestamp']
    

    def get_thumbnail(self, obj):
        img = obj.images.first()
        return img.image.url if img else None

class OservationReportsSerializer(serializers.ModelSerializer):
    predicted_species = serializers.CharField(source='species.scientific_name', read_only=True)
    thumbnail = serializers.SerializerMethodField()
    observation_id = serializers.IntegerField(source='observation.id', read_only=True)
    reporter = serializers.CharField(source='reporter.id', read_only=True)

    class Meta:
      model= ObservationReport
      fields = ['id', 'observation_id', 'predicted_species', 'thumbnail', 'reporter', 'note', 'created_at']

    def get_thumbnail(self, obj):
        img = obj.images.first()
        return img.image.url if img else None

class ResearcherAlertsSerializer(serializers.ModelSerializer):
    species_name = serializers.CharField(source='species.scientific_name', read_only=True)
    thumbnail = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()
    
    class Meta:
        model = Observation
        fields = ['id', 'species_name', 'flags', 'governorate', 'timestamp', 'thumbnail', 'longitude', 'latitude']
    
    def get_thumbnail(self, obj):
        img = obj.images.first()
        return img.image.url if img else None
    
    def get_flags(self, obj):
        flags = []
        if obj.species.is_endangered:
            flags.append('endangered')
        if obj.species.is_invasive:
            flags.append('invasive')
        
        return flags