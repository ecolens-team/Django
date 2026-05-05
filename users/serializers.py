from django.db import transaction
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from .models import User, ResearcherProfile
from .models import Follow, Conversation, Message

class CustomUserDetailsSerializer(UserDetailsSerializer):
    researcher_profile = serializers.SerializerMethodField()

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + ("role", "bio", "phone_number", "profile_picture", "researcher_profile", "is_active")
        read_only_fields = ("role",)

    def get_researcher_profile(self, obj):
        if obj.role == "RESEARCHER":
            profile = getattr(obj, "researcher_profile", None)
            if profile:
                return ResearcherProfileSerializer(profile).data
        return None


class CustomRegisterSerializer(RegisterSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default="USER")
    institute = serializers.CharField(required=False, allow_blank=True)
    credentials = serializers.FileField(required=False, allow_null=True)

    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def validate_role(self, value):
        if value == "ADMIN":
            raise serializers.ValidationError("You cannot register as admin.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        role = attrs.get("role", "USER")
        institute = attrs.get("institute")
        credentials = attrs.get("credentials")

        if role == "RESEARCHER":
            if not institute:
                raise serializers.ValidationError({"institute": "Institute is required for researchers."})
            if not credentials:
                raise serializers.ValidationError({"credentials": "Credentials file is required for researchers."})

        return attrs

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["role"] = self.validated_data.get("role", "USER")
        data["institute"] = self.validated_data.get("institute", "")
        data["credentials"] = self.validated_data.get("credentials")
        data['profile_picture'] = self.validated_data.get("profile_picture")
        data["first_name"] = self.validated_data.get('first_name', '')
        data["last_name"] = self.validated_data.get('last_name', '')
        data["phone_number"] = self.validated_data.get('phone_number', '')
        data["bio"] = self.validated_data.get('bio', '')
        return data

    @transaction.atomic
    def custom_signup(self, request, user):
        cleaned = self.get_cleaned_data()
        user.role = cleaned.get("role")
        user.first_name = cleaned.get("first_name", "")
        user.last_name = cleaned.get("last_name", "")
        user.phone_number = cleaned.get("phone_number", "")
        user.bio = cleaned.get("bio", "")
        user.profile_picture = cleaned.get('profile_picture')
        user.save()

        if cleaned["role"] == "RESEARCHER":
            ResearcherProfile.objects.create(
                user=user,
                institute=cleaned["institute"],
                credentials=cleaned["credentials"],
                application_status="PENDING",
            )



class ResearcherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearcherProfile
        fields = ('institute', 'credentials', 'application_status')


class ResearcherApplicationSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    username = serializers.ReadOnlyField(source='user.username')
    id = serializers.ReadOnlyField(source='user.id') 

    class Meta:
        model = ResearcherProfile
        fields = ('institute', 'credentials', 'application_status', 'full_name', 'username', 'id')
        read_only_fields = ('institute', 'full_name', 'username', 'credentials', 'id')
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

class UserProfileSerializer(serializers.ModelSerializer):
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    observations_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    profile_thumbnail = serializers.SerializerMethodField()

    def get_profile_thumbnail(self, obj):
        try:
            request = self.context.get('request')
            url = obj.thumbnail.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None

    class Meta:
        model = User
        fields = [
            'id', 'name', 'username', 'bio',
            'profile_picture', 'role', 'profile_thumbnail',
            'followers_count', 'following_count',
            'observations_count', 'is_following'
        ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_followers_count(self, obj):
        return obj.followers_set.count()

    def get_following_count(self, obj):
        return obj.following_set.count()

    def get_observations_count(self, obj):
        return obj.observations.count()

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=request.user, following=obj
            ).exists()
        return False

class BasicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile_picture']


class MessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = ['id', 'timestamp', 'sender', 'receiver', 'content']


class ConversationSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'user', 'last_message', 'updated_at']
    
    def get_last_message(self, obj):
        last = obj.messages.order_by('-timestamp').first()
        if last:
            return MessageSerializer(last).data
        else:
            return None
    
    def get_user(self, obj):
        req = self.context.get('request')
        other_user = obj.participants.exclude(id=req.user.id).first()

        return BasicUserSerializer(other_user).data

