from PIL import Image, ExifTags
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView, get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Observation, Species
from .serializers import ObservationSerializer, SpeciesSerializer, speciesProfileSerializer, SpeciesUpdateSerializer
from users.permissions import IsApprovedResearcher
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from .models import Like, Comment
from .serializers import CommentSerializer
from rest_framework.views import APIView
import os
import json
import torch
import torch.nn as nn
import open_clip
from peft import PeftModel

device = "cpu"
VERSION_FLAG = os.environ.get("BIOCLIP_VERSION", "2")
IS_BIOCLIP_2 = (str(VERSION_FLAG) == "2")


_ai_ready = False
SPECIES_LABELS = []
lora_model = None
preprocess = None
classification_head = None


def _load_ai():
    global _ai_ready, SPECIES_LABELS, lora_model, preprocess, classification_head

    print("--- SERVER STARTUP ---", flush=True)
    print(f"[INFO] Initializing AI.. (BioCLIP Version: {VERSION_FLAG})", flush=True)

    try:
        classes_path = os.path.join(settings.BASE_DIR, 'observations', 'ecolens_classes.json')
        with open(classes_path, 'r', encoding='utf-8') as f:
            SPECIES_LABELS = json.load(f)
        num_classes = len(SPECIES_LABELS)
    except Exception as e:
        print(f"Error loading classes: {e}", flush=True)
        SPECIES_LABELS = []
        num_classes = 0

    if IS_BIOCLIP_2:
        MODEL_STRING = 'hf-hub:imageomics/bioclip-2'
        HEAD_DIM = 768
        LORA_DIR = os.path.join(settings.BASE_DIR, 'observations', 'v4_epoch_5')
    else:
        MODEL_STRING = 'hf-hub:imageomics/bioclip'
        HEAD_DIM = 512
        LORA_DIR = os.path.join(settings.BASE_DIR, 'observations', '6')

    HEAD_PATH = os.path.join(LORA_DIR, 'head.pth')

    print("Loading Base model...", flush=True)
    base_model, _, preprocess = open_clip.create_model_and_transforms(MODEL_STRING, device=device)

    print(f"Attaching LoRA Adapters from {LORA_DIR}...", flush=True)
    if IS_BIOCLIP_2:
        lora_model = PeftModel.from_pretrained(base_model.visual, LORA_DIR)
    else:
        lora_model = PeftModel.from_pretrained(base_model, LORA_DIR)

    lora_model.to(device)
    lora_model.eval()

    print("Attaching Classification Head", flush=True)
    classification_head = nn.Linear(HEAD_DIM, num_classes, bias=False).to(device)
    classification_head.load_state_dict(torch.load(HEAD_PATH, map_location=device, weights_only=True))
    classification_head.eval()

    _ai_ready = True
    print("--- AI READY ---", flush=True)


class SpeciesListView(ListAPIView):
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer
    permission_classes = [AllowAny] 

class SpeciesDetailView(RetrieveAPIView):
    queryset = Species.objects.all()
    serializer_class = speciesProfileSerializer
    permission_classes = [AllowAny]


class IsResearcherOrAdmin(IsApprovedResearcher):
    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and getattr(user, 'role', None) == 'ADMIN':
            return True
        return super().has_permission(request, view)


class SpeciesUpdateView(UpdateAPIView):
    queryset = Species.objects.all()
    serializer_class = SpeciesUpdateSerializer
    permission_classes = [IsResearcherOrAdmin]
    http_method_names = ['patch']


class PredictSpeciesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            raw_image = Image.open(image_file)
            pil_image = raw_image.convert("RGB")
            image_tensor = preprocess(pil_image).unsqueeze(0).to(device)

            with torch.no_grad():
                if IS_BIOCLIP_2:
                    features = lora_model(image_tensor)
                else:
                    features = lora_model.encode_image(image_tensor)
                
                logits = classification_head(features)
                probabilities = logits.softmax(dim=-1)
            
            best_idx = probabilities.argmax().item()
            confidence = probabilities[0][best_idx].item()
            species_prediction = SPECIES_LABELS[best_idx]
            
            return Response({
                "species": species_prediction.replace("_", " "), 
                "confidence": confidence
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"AI Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FeedPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 200


class ObservationsView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ObservationSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        queryset = Observation.objects.all().order_by('-timestamp')

        user = self.request.query_params.get("user")
        species = self.request.query_params.get("species")
        min_confidence = self.request.query_params.get("min_confidence")
        ordering = self.request.query_params.get("ordering")

        if user:
            queryset = queryset.filter(user__username=user)
        if species:
            queryset = queryset.filter(
                species__common_name_en__icontains=species
            ) | queryset.filter(
                species__scientific_name__icontains=species
            )
        if min_confidence:
            queryset = queryset.filter(
                confidence_level__gte=float(min_confidence) / 100
            )
        if ordering == "-confidence_level":
            queryset = queryset.order_by("-confidence_level")

        return queryset

    def create(self, request, *args, **kwargs):
        image_file = request.FILES.get('images')
        if not image_file:
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)

        photo_timestamp = request.data.get('timestamp')

        if not photo_timestamp:
            try:
                raw_image = Image.open(image_file)
                raw_exif = raw_image.getexif()
                if raw_exif:
                    exif_data = {ExifTags.TAGS.get(k, k): v for k, v in raw_exif.items()}
                    date_str = exif_data.get('DateTimeOriginal') or exif_data.get('DateTime')
                    if date_str:
                        parsed_date = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        photo_timestamp = timezone.make_aware(parsed_date)
            except Exception as e:
                print(f"EXIF extraction failed: {e}")
        
        if not photo_timestamp:
            photo_timestamp = timezone.now()

        species_prediction = request.data.get('species_prediction', 'Unknown')
        confidence = request.data.get('confidence_level', 0.0)


        species_obj, created = Species.objects.get_or_create(
            scientific_name=species_prediction,
            defaults={'type': 'PLANT'} #fix this later
        ) 
        
        data = {
            'description': request.data.get('description', ''),
            'longitude': request.data.get('longitude'),
            'latitude': request.data.get('latitude'),
            'species': species_obj.id,
            'timestamp': photo_timestamp,
            'weather': request.data.get('weather', '') or '',
            'governorate': request.data.get('governorate', '') or '',
        }
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        observation = serializer.save(
            user=self.request.user,
            species=species_obj,
            confidence_level=confidence,
        )

        from .models import Image as ObsImage
        for img in request.FILES.getlist('images'):
            ObsImage.objects.create(
                observation=observation,
                image=img,
                date=photo_timestamp
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ObservationDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Observation.objects.all()
    serializer_class = ObservationSerializer


class VerifyObservationView(UpdateAPIView):
    queryset = Observation.objects.all()
    serializer_class = ObservationSerializer
    permission_classes = [IsApprovedResearcher]

    def update(self, request, *args, **kwargs):
        observation = self.get_object()
        new_species_id = request.data.get('species_id')

        try:
            new_species = Species.objects.get(id=new_species_id)
            observation.species = new_species
            observation.verified = True
            observation.save()
            return Response({"message": "Observation verified and updated successfully"})
            
        except Species.DoesNotExist:
            return Response({"error": "Species not found."}, status=status.HTTP_404_NOT_FOUND)


class LikeObservationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        observation = get_object_or_404(Observation, pk=pk)
        like, created = Like.objects.get_or_create(user=request.user, observation=observation)
        if not created:
            like.delete()
            return Response({'status': 'unliked'}, status=status.HTTP_200_OK)
        return Response({'status': 'liked'}, status=status.HTTP_201_CREATED)

class CommentListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(observation_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        observation = get_object_or_404(Observation, pk=self.kwargs['pk'])
        serializer.save(user=self.request.user, observation=observation)

class TaxaOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        level = request.query_params.get('level')
        q = request.query_params.get('q')
        options = None

        if level == 'species':
            options = Species.objects.filter(scientific_name__icontains=q).values_list('scientific_name', flat=True).distinct()[0:10]
        elif level == 'genus':
            options = Species.objects.filter(genus__icontains=q).values_list('genus', flat=True).distinct()[0:10]
        elif level == 'family':
            options = Species.objects.values_list('family', flat=True).distinct()
        elif level == 'order':
            options = Species.objects.values_list('order', flat=True).distinct()
        else:
            options = ['insecta', 'plantae']

        return Response(options)

        