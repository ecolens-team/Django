from rest_framework import serializers
from .models import Observation, Species, Image
from users.serializers import CustomUserDetailsSerializer
from django.db.models import Count, Max
from django.db.models.functions import ExtractMonth
from django.core.files.storage import default_storage

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
    species = SpeciesSerializer(read_only=True)
    user = CustomUserDetailsSerializer(read_only=True)

    class Meta:
        model = Observation
        fields = [
            'id', 'user', 'species', 'timestamp', 'longitude', 
            'latitude', 'description', 'confidence_level', 'verified', 'images', 'governorate', 'weather'
        ]
        read_only_fields = ['user', 'confidence_level', 'verified']

class speciesProfileSerializer(serializers.ModelSerializer):
    scientificName = serializers.CharField(source='scientific_name')
    commonNameAr = serializers.CharField(source='common_name_ar')
    commonNameEn = serializers.CharField(source='common_name_en')
    imageUrl = serializers.URLField(source='best_image_url', read_only=True)
    
    description = serializers.SerializerMethodField()
    ecology = serializers.SerializerMethodField()
    community = serializers.SerializerMethodField()
    dataInsights = serializers.SerializerMethodField()

    class Meta:
        model = Species
        fields = ['id', 'scientificName', 'commonNameAr', 'commonNameEn', 'imageUrl', 
                  'description', 'ecology', 'community', 'dataInsights']
    
    def get_description(self, obj):
        return {
            "text": obj.description,
            "isVerified": obj.description_is_verified
        }
    
    def get_ecology(self, obj): 
        top_governorates = obj.observations.exclude(governorate__isnull=True) \
            .values('governorate') \
            .annotate(count=Count('id')) \
            .order_by('-count')[:3]
        
        return {
            "isEndemic": obj.is_endemic,
            "isInvasive": obj.is_invasive,
            "isEndangered": obj.is_endangered,
            "topGovernorates": [t['governorate'] for t in top_governorates]
        }
    
    def get_community(self, obj):
        total = obj.observations.count()

        top_users = (
            obj.observations
            .values('user_id') 
            .annotate(
                obs=Count('id'),
                name=Max('user__username'),  
                avatar=Max('user__profile_picture')
            )
            .order_by('-obs')[:3]
        )

        observers_data = []
        for u in top_users:
            if u.get('avatar'):
                avatar_url = default_storage.url(u['avatar'])
            else:
                avatar_url = f"https://ui-avatars.com{u['name']}"
            
            observers_data.append({
                "name": u['name'], 
                "obs": u['obs'], 
                "avatar": avatar_url
            })

        return {
            "totalObservations": total,
            "topObservers": observers_data,
            "topExperts": [], # todo this would pull verfied researchers who say this species is in thier expertise plus who have verified it the most
            "activeQuests": [] # todo add this after updating quest model so that Quest.objects.filter(target_species=obj)// it could have more than one species too
        }
    
    def get_dataInsights(self, obj):
        month_counts = obj.observations.annotate(month=ExtractMonth('timestamp')) \
            .values('month') \
            .annotate(count=Count('id'))
        
        seasonality = [0] * 12 
        for item in month_counts:
            if item['month']:
                seasonality[item['month'] - 1] = item['count']

        weather_counts = obj.observations.exclude(weather__isnull=True) \
            .values('weather') \
            .annotate(count=Count('id'))
        
        total_weather_obs = sum([w['count'] for w in weather_counts])
        weather_data = []
        
        color_map = {
            "Sunny": "bg-amber-400",
            "Partially Cloudy": "bg-sky-300",
            "Cloudy": "bg-gray-400",
            "Foggy": "bg-slate-300",
            "Rainy": "bg-blue-500",
            "Snowy": "bg-sky-100",
            "Stormy": "bg-slate-700",
            "Hazy": "bg-stone-400"
        }
        
        for w in weather_counts:
            percent = int((w['count'] / total_weather_obs) * 100) if total_weather_obs > 0 else 0
            weather_data.append({
                "label": w['weather'],
                "percent": percent,
                # Fallback to teal
                "color": color_map.get(w['weather'], "bg-teal-500")
            })


        weather_data.sort(key=lambda x: x['percent'], reverse=True)

        return {
            "seasonality": seasonality,
            "weather": weather_data
        }
    