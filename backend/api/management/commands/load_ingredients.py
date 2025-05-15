# backend/api/management/commands/load_ingredients.py
import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from api.models import Ingredient


class Command(BaseCommand):
    help = (
        'Loads ingredients from a JSON file into the database using '
        'batched bulk_create for high performance. '
        'Use --batch-size to control the number of items per DB query. '
        'Handles duplicates by ignoring them if they already exist '
        '(based on unique constraint on name and measurement_unit).'
    )

    default_json_path = os.path.join(
        settings.BASE_DIR, 'data', 'ingredients.json')

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            help='Path to the JSON file',
            default=self.default_json_path
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            help=('Number of ingredients to process'
                  'in a single bulk_create call.'),
            default=1000
        )

    def handle(self, *args, **options):
        try:
            file_path = options['path']
            batch_size = options['batch_size']

            self.stdout.write(self.style.SUCCESS(
                f'Starting to load ingredients from {file_path}'
                f' with batch size {batch_size}'))

            with open(file_path, mode='r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)

            with transaction.atomic():
                ingredients_to_create = [
                    Ingredient(
                        name=item.get('name', '').strip(),
                        measurement_unit=item.get(
                            'measurement_unit', '').strip()
                    )
                    for item in data
                ]

                if not ingredients_to_create:
                    self.stdout.write(self.style.WARNING(
                        "No valid ingredients to import after preparation."))
                else:

                    created_objects = Ingredient.objects.bulk_create(
                        ingredients_to_create,
                        ignore_conflicts=True
                    )

                    num_actually_created = len(created_objects)
                    num_attempted = len(ingredients_to_create)

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Attempted to import"
                            f" {num_attempted} ingredients. "
                            f"Added {num_actually_created} new ingredients. "
                        )
                    )

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f'An unexpected error occurred'
                f' while processing {file_path}: {e}'
            ))
