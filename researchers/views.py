import csv
from datetime import timedelta
from django.db.models import Count, Case, When, IntegerField, Q
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.shortcuts import get_object_or_404
from users.models import ResearcherSpecialization
from users.permissions import IsApprovedResearcher
from observations.models import Observation, ObservationReport, Species
from gamification.models import Quest
from .serializers import ObservationQueueSerializer, OservationReportsSerializer, ResearcherAlertsSerializer


class IsResearcherOrAdmin(IsApprovedResearcher):
    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and getattr(user, 'role', None) == 'ADMIN':
            return True
        return super().has_permission(request, view)


def build_specialization_q(spec_pairs, for_observations=False):
    if not spec_pairs:
        return Q()
    query = Q()
    for level, name in spec_pairs:
        if level == 'CLASS':
            type_val = 'INSECT' if name.upper() == 'INSECTA' else 'PLANT'
            field = 'species__type' if for_observations else 'type'
            query |= Q(**{field: type_val})
        else:
            field_map = {
                'SPECIES': 'species__scientific_name' if for_observations else 'scientific_name',
                'GENUS': 'species__genus' if for_observations else 'genus',
                'FAMILY': 'species__family' if for_observations else 'family',
                'ORDER': 'species__order' if for_observations else 'order',
            }
            if level in field_map:
                query |= Q(**{field_map[level]: name})
    return query


def get_researcher_spec_pairs(researcher):
    specs = ResearcherSpecialization.objects.filter(researcher=researcher)
    return [(s.level, s.name) for s in specs]


def get_researcher_specialization_q(researcher, is_filtering_observations=False):
    pairs = get_researcher_spec_pairs(researcher)
    if not pairs:
        return Q()
    return build_specialization_q(pairs, for_observations=is_filtering_observations)


def specialization_species_qs(researcher):
    pairs = get_researcher_spec_pairs(researcher)
    if not pairs:
        return Species.objects.all()
    return Species.objects.filter(build_specialization_q(pairs))



class ResearcherStatsView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        spec_q = get_researcher_specialization_q(request.user, is_filtering_observations=True)

        queue_count = Observation.objects.filter(spec_q, verified=False).distinct().count()

        reports_count = ObservationReport.objects.filter(
            resolved=False,
            observation_id__in=Observation.objects.filter(spec_q).values('id')
        ).count()

        week_ago = timezone.now() - timedelta(days=7)
        alerts_count = Observation.objects.filter(
            spec_q,
            timestamp__gte=week_ago,
        ).filter(
            Q(species__is_endangered=True) | Q(species__is_invasive=True)
        ).count()

        quests_count = Quest.objects.filter(status='ACTIVE', researcher=request.user).count()
        

        return Response({
            'queue_count': queue_count,
            'reports_count': reports_count,
            'alerts_count': alerts_count,
            'active_quests_count': quests_count
        })


class QueuePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 50


class ResearcherQueueView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        spec_q = get_researcher_specialization_q(request.user, is_filtering_observations=True)
        observations = (
            Observation.objects
            .filter(spec_q, verified=False)
            .select_related('species', 'user')
            .prefetch_related('images', 'reports')
            .annotate(report_count=Count('reports', filter=Q(reports__resolved=False)))
            .order_by('confidence_level', '-report_count')  # low confidence first
        )

        paginator = QueuePagination()
        page = paginator.paginate_queryset(observations, request)
        
        serializer = ObservationQueueSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)



class ResearcherReportsView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        spec_q = get_researcher_specialization_q(request.user, is_filtering_observations=True)

        reports = (
            ObservationReport.objects
            .filter(observation__in=Observation.objects.filter(spec_q), resolved=False)
            .select_related('observation__species', 'reporter', 'observation')
            .prefetch_related('observation__images')
            .order_by('-created_at')
        )

        paginator = QueuePagination()
        page = paginator.paginate_queryset(reports, request)

        serializer = OservationReportsSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)


class ResolveReportView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def patch(self, request, pk):
        report = get_object_or_404(ObservationReport, pk=pk)

        report.resolved = True
        report.resolved_by = request.user
        report.save()
        return Response({'resolved': True})


class SubmitObservationReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, observation_id):
        observation = get_object_or_404(Observation, pk=observation_id)

        note = request.data.get('note', '').strip()
        _, created = ObservationReport.objects.get_or_create(
            observation=observation,
            reporter=request.user,
            defaults={'note': note},
        )
        if not created:
            return Response({'error': 'You already reported this observation'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'reported': True}, status=status.HTTP_201_CREATED)



class ResearcherInsightsView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        specs_param = request.query_params.get('specs', '')

        if specs_param:
            pairs = []
            for pair in specs_param.split(','):
                if ':' not in pair:
                    continue
                level, name = pair.split(':', 1)
                pairs.append((level.strip().upper(), name.strip()))
        else:
            pairs = get_researcher_spec_pairs(request.user)

        if pairs:
            obs_q = build_specialization_q(pairs, for_observations=True)
            species_q = build_specialization_q(pairs, for_observations=False)
        else:
            obs_q = Q()
            species_q = Q()

        species_qs = Species.objects.filter(species_q) if pairs else Species.objects.all()
        total_species = species_qs.count()
        observed_species = species_qs.filter(observations__isnull=False).distinct().count()

        obs_qs = Observation.objects.filter(obs_q)
        total_observations = obs_qs.count()

        top_governorates = list(
            obs_qs.exclude(governorate__isnull=True)
            .values('governorate')
            .annotate(count=Count('id'))
            .order_by('-count')[:6]
        )

        twelve_months_ago = timezone.now() - timedelta(days=365)
        monthly = list(
            obs_qs.filter(timestamp__gte=twelve_months_ago)
            .annotate(month=ExtractMonth('timestamp'), year=ExtractYear('timestamp'))
            .values('year', 'month')
            .annotate(count=Count('id'))
            .order_by('year', 'month')
        )

        metrics = obs_qs.aggregate(
            b1=Count(Case(When(confidence_level__lt=0.2, then=1), output_field=IntegerField())),
            b2=Count(Case(When(confidence_level__gte=0.2, confidence_level__lt=0.4, then=1), output_field=IntegerField())),
            b3=Count(Case(When(confidence_level__gte=0.4, confidence_level__lt=0.6, then=1), output_field=IntegerField())),
            b4=Count(Case(When(confidence_level__gte=0.6, confidence_level__lt=0.8, then=1), output_field=IntegerField())),
            b5=Count(Case(When(confidence_level__gte=0.8, then=1), output_field=IntegerField()))
        )
        confidence_dist = [
            {'bucket': '0–20%', 'count': metrics['b1']},
            {'bucket': '20–40%', 'count': metrics['b2']},
            {'bucket': '40–60%', 'count': metrics['b3']},
            {'bucket': '60–80%', 'count': metrics['b4']},
            {'bucket': '80–100%', 'count': metrics['b5']},
        ]

        verified_count = obs_qs.filter(verified=True).count()
        verification_rate = (verified_count / total_observations * 100) if total_observations > 0 else 0

        weather_stats = list(
            obs_qs.exclude(weather__isnull=True).exclude(weather='')
            .values('weather')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        type_breakdown = {
            'plants': obs_qs.filter(species__type='PLANT').count(),
            'insects': obs_qs.filter(species__type='INSECT').count(),
        }

        top_species = list(
            obs_qs.filter(species__isnull=False)
            .values('species__id', 'species__scientific_name', 'species__common_name_en')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        taxa_breakdown = []
        for level, name in pairs:
            single_q = build_specialization_q([(level, name)], for_observations=True)
            count = Observation.objects.filter(single_q).count()
            taxa_breakdown.append({'level': level, 'name': name, 'count': count})
        taxa_breakdown.sort(key=lambda x: x['count'], reverse=True)

        locations = list(
            obs_qs.filter(latitude__isnull=False, longitude__isnull=False)
            .values('id', 'latitude', 'longitude')[:500]
        )

        return Response({
            'species': {
                'total': total_species,
                'observed': observed_species,
                'unobserved': total_species - observed_species,
            },
            'total_observations': total_observations,
            'top_governorates': top_governorates,
            'monthly_observations': monthly,
            'confidence_distribution': confidence_dist,
            'verification_rate': round(verification_rate, 1),
            'weather_stats': weather_stats,
            'type_breakdown': type_breakdown,
            'top_species': top_species,
            'taxa_breakdown': taxa_breakdown,
            'observation_locations': locations,
        })



class ResearcherAlertsView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)
        spec_q = get_researcher_specialization_q(request.user, is_filtering_observations=True)

        alerts = (
            Observation.objects
            .filter(spec_q, timestamp__gte=week_ago)
            .filter(Q(species__is_endangered=True) | Q(species__is_invasive=True))
            .select_related('species')
            .prefetch_related('images')
            .order_by('-timestamp')[:20]
        )

        serializer = ResearcherAlertsSerializer(alerts, many=True)

        return Response(serializer.data)



class CsvBuffer:
    def write(self, value):
        return value


class ResearcherExportView(APIView):
    permission_classes = [IsResearcherOrAdmin]

    def get(self, request):
        spec_q = get_researcher_specialization_q(request.user, is_filtering_observations=True)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        governorate = request.query_params.get('governorate')
        verified_only = request.query_params.get('verified_only') == 'true'

        level = request.query_params.get('level', '').upper()
        name = request.query_params.get('name', '').strip()
        if level and name:
            type_map = {'INSECTA': 'INSECT', 'PLANTAE': 'PLANT'}
            field_map = {
                'SPECIES': 'species__scientific_name',
                'GENUS': 'species__genus',
                'FAMILY': 'species__family',
                'ORDER': 'species__order',
                'CLASS': 'species__type',
            }
            if level in field_map:
                lookup_val = type_map.get(name.upper(), name)
                spec_q &= Q(**{field_map[level]: lookup_val})

        qs = Observation.objects.filter(spec_q).select_related('species', 'user')

        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        if governorate:
            qs = qs.filter(governorate=governorate)
        if verified_only:
            qs = qs.filter(verified=True)

        qs = qs.order_by('timestamp')

        def stream():
            buf = CsvBuffer()
            writer = csv.writer(buf)
            yield writer.writerow([
                'observation_id', 'species_scientific_name', 'species_type',
                'confidence', 'latitude', 'longitude', 'governorate',
                'weather', 'date', 'verified', 'observer_username',
            ])
            for obs in qs.iterator(chunk_size=500):
                yield writer.writerow([
                    obs.id,
                    obs.species.scientific_name if obs.species else '',
                    obs.species.type if obs.species else '',
                    obs.confidence_level,
                    obs.latitude,
                    obs.longitude,
                    obs.governorate or '',
                    obs.weather or '',
                    obs.timestamp.strftime('%Y-%m-%d %H:%M'),
                    obs.verified,
                    obs.user.username,
                ])

        response = StreamingHttpResponse(stream(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ecolens_observations.csv"'
        return response
