# backend/api/utils.py
from django.db.models import Sum
from .models import RecipeIngredient


def generate_shopping_list_text(user):
    """Generates a text representation of the user's shopping list."""
    ingredients = RecipeIngredient.objects.filter(
        recipe__in_shopping_cart_by__user=user
    ).values(
        'ingredient__name',
        'ingredient__measurement_unit'
    ).annotate(
        total_amount=Sum('amount')
    ).order_by('ingredient__name')

    shopping_list = "Список покупок Foodgram:\n\n"
    if not ingredients:
        return shopping_list + "Ваш список покупок пуст."

    for item in ingredients:
        name = item['ingredient__name']
        unit = item['ingredient__measurement_unit']
        amount = item['total_amount']
        shopping_list += f"- {name} ({unit}) — {amount}\n"

    return shopping_list
