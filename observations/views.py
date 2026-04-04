from PIL import Image, ExifTags
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Observation, Species
from .serializers import ObservationSerializer, SpeciesSerializer
from users.permissions import IsApprovedResearcher
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage
import os
import json
import torch
import open_clip


print("--- SERVER STARTUP ---")
device = "cpu"

model, _, preprocess = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip', device=device)
tokenizer = open_clip.get_tokenizer('hf-hub:imageomics/bioclip')

try:
    json_path = os.path.join(settings.BASE_DIR, 'species.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
        SPECIES_LABELS = data.get('plants', []) + data.get('insects', [])
except Exception as e:
    print(f"Error loading JSON: {e}. Using fallback.")
    SPECIES_LABELS = ['black iris', 'bee', 'beetle']


CACHE_PATH = os.path.join(settings.BASE_DIR, 'species_embeddings.pt')
TEXT_FEATURES = None

TEMPLATES = [
    lambda c: f'a photo of a {c}.',
    lambda c: f'a close-up photo of a {c}.',
    lambda c: f'a photo of the {c}.',
    lambda c: f'the {c} in the wild.',
    lambda c: f'a specimen of {c}.',
    lambda c: f'it is a {c}.',
]

def load_or_compute_embeddings():
    global TEXT_FEATURES
    
    if os.path.exists(CACHE_PATH):
        print(f"Found cached embeddings at {CACHE_PATH}...")
        try:
            cached_data = torch.load(CACHE_PATH, weights_only=True)
            if cached_data.shape[1] == len(SPECIES_LABELS):
                return cached_data.to(device)
            else:
                print(f"Cache mismatch (Saved: {cached_data.shape[1]}, Current: {len(SPECIES_LABELS)}). Recomputing...")
        except Exception as e:
            print(f"Corrupt cache: {e}. Recomputing...")

    print(f"Computing embeddings for {len(SPECIES_LABELS)} species...")
    
    with torch.no_grad():
        all_features = []
        for i, species_name in enumerate(SPECIES_LABELS):
            if i % 100 == 0: 
                print(f"Processing {i}/{len(SPECIES_LABELS)}...")

            texts = [template(species_name) for template in TEMPLATES]
            tokens = tokenizer(texts)
            class_embeddings = model.encode_text(tokens)
            class_embeddings /= class_embeddings.norm(dim=-1, keepdim=True)

            class_embedding = class_embeddings.mean(dim=0)
            class_embedding /= class_embedding.norm()
            all_features.append(class_embedding)

        features_matrix = torch.stack(all_features, dim=1).to(device)
        
        torch.save(features_matrix, CACHE_PATH)
        print(f"Saved embeddings to {CACHE_PATH}")
        
        return features_matrix


TEXT_FEATURES = load_or_compute_embeddings()
print("--- AI READY ---")


class SpeciesListView(ListAPIView):
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer
    permission_classes = [AllowAny] 

class SpeciesDetailView(RetrieveAPIView):
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer
    permission_classes = [AllowAny]

from rest_framework.views import APIView

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
                image_features = model.encode_image(image_tensor)
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_probs = (100.0 * image_features @ TEXT_FEATURES).softmax(dim=-1)
            
            best_idx = text_probs.argmax().item()
            confidence = text_probs[0][best_idx].item()
            species_prediction = SPECIES_LABELS[best_idx]
            
            return Response({
                "species": species_prediction, 
                "confidence": confidence
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"AI Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ObservationsView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Observation.objects.all().order_by('-timestamp')
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ObservationSerializer

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
            'timestamp': photo_timestamp
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