import json
import os
from django.core.management.base import BaseCommand
from observations.models import Species


class Command(BaseCommand):
    help = 'Seeds the database with species data from species_summaries.json'

    def handle(self, *args, **kwargs):
        json_path = os.path.join(os.path.dirname(__file__), '../../species_summaries.json')

        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f"File not found: {json_path}"))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write(f"Seeding {len(data)} species...")
        created_count = 0
        updated_count = 0

        for item in data:
            clean_name = item['scientific_name'].replace('_', ' ')
            species_type = item.get('type', 'PLANT')
            if species_type not in ('PLANT', 'INSECT'):
                species_type = 'PLANT'

            obj, created = Species.objects.update_or_create(
                scientific_name=clean_name,
                defaults={
                    'type': species_type,
                    'description': item.get('summary', ''),
                    'common_name_en': item.get('common_name_en', ''),
                    'is_endangered': item.get('is_endangered', False),
                    'genus': item.get('genus', ''),
                    'family': item.get('family', ''),
                    'order': item.get('order', ''),
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done — {created_count} created, {updated_count} updated."
        ))
