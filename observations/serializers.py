from rest_framework import serializers
from .models import Observation, Species, Image, Comment, Like
from users.serializers import CustomUserDetailsSerializer
from django.db.models import Count, Max, Q
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
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    has_liked = serializers.SerializerMethodField()

    images = ImageSerializer(many=True, read_only=True) 
    species = SpeciesSerializer(read_only=True)
    user = CustomUserDetailsSerializer(read_only=True)

    class Meta:
        model = Observation
        fields = [
            'id', 'user', 'species', 'timestamp', 'longitude', 
            'latitude', 'description', 'confidence_level', 'verified', 'images', 'governorate', 'weather',
            'likes_count', 'comments_count', 'has_liked'
        ]
        read_only_fields = ['user', 'confidence_level', 'verified']

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_has_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

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

        # Cascade: species → genus → family → order → class
        # Return top 3, preferring the most specific match
        from users.models import ResearcherSpecialization
        type_to_class = {'PLANT': 'Plantae', 'INSECT': 'Insecta'}
        cascade_filters = [
            Q(level='SPECIES', name=obj.scientific_name),
            Q(level='GENUS',   name=obj.genus),
            Q(level='FAMILY',  name=obj.family),
            Q(level='ORDER',   name=obj.order),
            Q(level='CLASS',   name=type_to_class.get(obj.type, '')),
        ]
        seen_ids = set()
        experts_data = []
        for filt in cascade_filters:
            if len(experts_data) >= 3:
                break
            slots = 3 - len(experts_data)
            specs = (
                ResearcherSpecialization.objects
                .filter(filt)
                .filter(researcher__role='RESEARCHER')
                .exclude(researcher_id__in=seen_ids)
                .select_related('researcher')[:slots]
            )
            for spec in specs:
                r = spec.researcher
                if r.profile_picture:
                    avatar = default_storage.url(r.profile_picture.name)
                else:
                    avatar = f"https://ui-avatars.com/api/?name={r.username}&background=0d9488&color=fff"
                experts_data.append({
                    "name": r.username,
                    "title": f"{spec.level.capitalize()}: {spec.name}",
                    "avatar": avatar,
                })
                seen_ids.add(r.pk)

        return {
            "totalObservations": total,
            "topObservers": observers_data,
            "topExperts": experts_data,
            "activeQuests": []
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
    
class SpeciesUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = ['description', 'description_is_verified', 'is_endangered', 'is_invasive', 'is_endemic', 'common_name_en', 'common_name_ar']

class CommentSerializer(serializers.ModelSerializer):
    user = CustomUserDetailsSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'observation', 'content', 'timestamp']
        read_only_fields = ['user', 'observation']

class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'observation', 'timestamp']
        read_only_fields = ['user', 'observation']
