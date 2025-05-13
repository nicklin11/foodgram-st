# backend/api/management/commands/load_ingredients.py
import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction, IntegrityError
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
            help='''Number of ingredients to process
             in a single bulk_create call.''',
            default=1000
        )

    def handle(self, *args, **options):
        try:
            file_path = options['path']
            batch_size = options['batch_size']

            self.stdout.write(self.style.SUCCESS(
                f'''Starting to load ingredients from {file_path}
                with batch size {batch_size}'''))

            ingredients_buffer = []
            total_items_from_file = 0
            total_newly_added = 0
            total_skipped_invalid_data = 0
            with open(file_path, mode='r', encoding='utf-8') as jsonfile:
                try:
                    data = json.load(jsonfile)
                except json.JSONDecodeError as e:
                    raise CommandError(
                        f'Error decoding JSON from {file_path}: {e}')

                if not isinstance(data, list):
                    raise CommandError(
                        f'''Invalid JSON format in {file_path}:
                         Expected a list of ingredients.'''
                    )

                total_items_from_file = len(data)
                if total_items_from_file == 0:
                    self.stdout.write(self.style.NOTICE(
                        'JSON file is empty. No ingredients to load.'))
                    return

                with transaction.atomic():
                    for i, item in enumerate(data):
                        name = item.get('name')
                        measurement_unit = item.get('measurement_unit')

                        name = name.strip()
                        measurement_unit = measurement_unit.strip()

                        ingredients_buffer.append(
                            Ingredient(
                                name=name, measurement_unit=measurement_unit)
                        )

                        if len(ingredients_buffer) >= batch_size or (
                                i == total_items_from_file - 1
                                and ingredients_buffer):
                            try:
                                created_batch_objects = (
                                    Ingredient.objects.bulk_create(
                                        ingredients_buffer,
                                        ignore_conflicts=True
                                    )
                                )
                                num_actually_created = len(
                                    created_batch_objects)
                                total_newly_added += num_actually_created

                                num_in_batch = len(ingredients_buffer)
                                num_conflicted_in_batch = (
                                    num_in_batch - num_actually_created)

                                self.stdout.write(
                                    f'''  Processed batch
                                    of {num_in_batch} items: '''
                                    f'Added {num_actually_created} new, '
                                    f'''{num_conflicted_in_batch} already
                                     existed or conflicted.'''
                                )
                                ingredients_buffer = []  # Clear buffer
                            except IntegrityError as e:
                                self.stderr.write(self.style.ERROR(
                                    f'''IntegrityError during bulk_create
                                    for a batch. '''
                                    f'''This might indicate an issue not
                                    covered by ignore_conflicts. Error: {e}'''
                                ))
                                total_skipped_invalid_data += len(
                                    ingredients_buffer)
                                ingredients_buffer = []
        except CommandError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            raise e
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f'''An unexpected error occurred
                while processing {file_path}: {e}'''
            ))
            # Wrap in CommandError for consistent command failure reporting
            raise CommandError(
                f'Unexpected error during ingredient loading: {e}')

        # Calculate final counts
        total_valid_items_processed = (
            total_items_from_file - total_skipped_invalid_data)
        total_existed_or_conflicted = max(
            0, total_valid_items_processed - total_newly_added)

        self.stdout.write(self.style.SUCCESS(
            '\n' + '=' * 30 + ' Load Summary ' + '=' * 30))
        self.stdout.write(self.style.SUCCESS(
            f'  Total items in JSON file: {total_items_from_file}'))
        self.stdout.write(self.style.SUCCESS(
            f'  Newly added ingredients: {total_newly_added}'))
        if total_skipped_invalid_data > 0:
            self.stdout.write(self.style.WARNING(
                f'''  Skipped (invalid data or batch errors):
                 {total_skipped_invalid_data}'''))
        if total_existed_or_conflicted > 0:
            self.stdout.write(self.style.NOTICE(
                f'''  Skipped (already existed or conflicted):
                 {total_existed_or_conflicted}'''))

        if total_newly_added == 0 and total_valid_items_processed > 0:
            self.stdout.write(self.style.NOTICE(
                '''No new ingredients were added from the valid items.
                 All might already exist or conflicted.'''
            ))
        self.stdout.write(self.style.SUCCESS('Finished loading ingredients.'))
