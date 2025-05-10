# backend/api/management/commands/load_ingredients.py
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from api.models import Ingredient  # Adjust import path if necessary


class Command(BaseCommand):
    help = 'Loads ingredients from a CSV file into the database'

    # Define default path relative to BASE_DIR/data
    default_csv_path = os.path.join(
        settings.BASE_DIR, 'data', 'ingredients.csv')

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            help='Path to the CSV file',
            default=self.default_csv_path
        )

    def handle(self, *args, **options):
        file_path = options['path']

        if not os.path.exists(file_path):
            raise CommandError(f'File not found at path: {file_path}')

        self.stdout.write(self.style.SUCCESS(
            f'Starting to load ingredients from {file_path}'))
        loaded_count = 0
        skipped_count = 0

        try:
            with open(file_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                # Optional: Skip header row if your CSV has one
                # next(reader, None)

                for row in reader:
                    if len(row) != 2:
                        self.stdout.write(self.style.WARNING(
                            f'Skipping invalid row: {row}'))
                        skipped_count += 1
                        continue

                    name, measurement_unit = row
                    name = name.strip()
                    measurement_unit = measurement_unit.strip()

                    if not name or not measurement_unit:
                        self.stdout.write(self.style.WARNING(
                            f'Skipping row with empty values: {row}'))
                        skipped_count += 1
                        continue

                    try:
                        # Use get_or_create to avoid duplicates based on unique constraint
                        obj, created = Ingredient.objects.get_or_create(
                            name=name,
                            measurement_unit=measurement_unit,
                            # Optional: defaults={} can be used if you have default values
                        )
                        if created:
                            loaded_count += 1
                            self.stdout.write(self.style.SUCCESS(
                                f'  + Added: {name} ({measurement_unit})'))
                        else:
                            self.stdout.write(self.style.NOTICE(
                                f'  = Exists: {name} ({measurement_unit})'))
                            skipped_count += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f'Error adding ingredient "{name}": {e}'))
                        skipped_count += 1

        except FileNotFoundError:
            raise CommandError(f'File not found at path: {file_path}')
        except Exception as e:
            raise CommandError(f'An error occurred: {e}')

        self.stdout.write(self.style.SUCCESS(f'Finished loading ingredients.'))
        self.stdout.write(self.style.SUCCESS(f'  Added: {loaded_count}'))
        self.stdout.write(self.style.WARNING(
            f'  Skipped/Existing: {skipped_count}'))
