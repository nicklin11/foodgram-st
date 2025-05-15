from django.db.models import Sum
from django.utils import timezone
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
    ).select_related('author').only(
        'name', 'author__username'
    ).order_by('name')

    current_date = timezone.now().strftime("%d.%m.%Y %H:%M")
    report_header = f"Список покупок Foodgram ({user.username})\n"
    f"Дата: {current_date}"

    ingredient_item_lines = [
        f"{i}. {item['ingredient__name'].capitalize()}"
        f" ({item['ingredient__measurement_unit']}) — {item['total_amount']}"
        for i, item in enumerate(aggregated_ingredients, 1)
    ]

    recipe_item_lines = [
        f"{i}. {recipe.name} (автор: {recipe.author.username})"
        for i, recipe in enumerate(recipes_in_cart, 1)
    ]

    return "\n".join(
        [report_header] + (
            ["\n\nВаш список покупок пуст."]
            if not aggregated_ingredients else
            (
                ["\n\nПродукты для покупки:"]
                + ingredient_item_lines
                + (
                    ["\n\nДля приготовления следующих рецептов:"]
                    + recipe_item_lines
                    if recipes_in_cart else []
                )
            )
        )
    )
