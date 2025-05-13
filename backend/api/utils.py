# backend/api/utils.py
from django.db.models import Sum
from django.utils import timezone  # For date
# Import Recipe for fetching details
from .models import RecipeIngredient, Recipe


def generate_shopping_list_text(user):
    """Generates a text representation of the user's shopping list."""
    aggregated_ingredients = RecipeIngredient.objects.filter(
        recipe__in_shopping_cart_set__user=user
    ).values(
        'ingredient__name',
        'ingredient__measurement_unit'
    ).annotate(
        total_amount=Sum('amount')
    ).order_by('ingredient__name')

    recipes_in_cart = Recipe.objects.filter(
        in_shopping_cart_set__user=user
    ).select_related('author').only('name',
                                    'author__username').order_by('name')

    current_date = timezone.now().strftime("%d.%m.%Y %H:%M")

    header = f'''Список покупок Foodgram ({user.username})
    \nДата: {current_date}\n'''

    if not aggregated_ingredients:
        return header + "\nВаш список покупок пуст."

    ingredient_lines = ["\nПродукты для покупки:"]
    for i, item in enumerate(aggregated_ingredients, 1):
        name = item['ingredient__name'].capitalize()
        unit = item['ingredient__measurement_unit']
        amount = item['total_amount']
        ingredient_lines.append(f"{i}. {name} ({unit}) — {amount}")

    recipe_lines = []
    if recipes_in_cart:
        recipe_lines.append("\nДля приготовления следующих рецептов:")
        for i, recipe in enumerate(recipes_in_cart, 1):
            recipe_lines.append(
                f"{i}. {recipe.name} (автор: {recipe.author.username})")

    # Combine all parts
    full_list = [header] + ingredient_lines + recipe_lines
    return "\n".join(full_list)
