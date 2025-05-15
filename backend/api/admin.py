# backend/api/admin.py
import numpy as np
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html, mark_safe
from .models import (Ingredient, Recipe, RecipeIngredient,
                     Favorite, ShoppingCart, Subscription)

# For RecipeAdmin cooking_time filter


class CookingTimeRangeFilter(admin.SimpleListFilter):
    title = 'cooking time'
    parameter_name = 'cooking_time_range'

    # Thresholds will be calculated dynamically
    _short_threshold = None
    _medium_threshold = None

    def _calculate_thresholds(self, queryset):
        """
        Calculates dynamic thresholds based on the current recipe set.
        Uses 33rd and 66th percentiles to divide into three groups.
        """
        if CookingTimeRangeFilter._short_threshold is not None and \
           CookingTimeRangeFilter._medium_threshold is not None:
            return

        # Get all distinct cooking times
        cooking_times = sorted(
            list(queryset.values_list('cooking_time', flat=True).distinct()))

        if not cooking_times or len(cooking_times) < 3:
            CookingTimeRangeFilter._short_threshold = 20
            CookingTimeRangeFilter._medium_threshold = 45
            if len(cooking_times) == 1:
                CookingTimeRangeFilter._short_threshold = cooking_times[0]
                CookingTimeRangeFilter._medium_threshold = cooking_times[0] + 1
            elif len(cooking_times) == 2:
                CookingTimeRangeFilter._short_threshold = cooking_times[0]
                CookingTimeRangeFilter._medium_threshold = cooking_times[1]
            return

        p33 = int(np.percentile(cooking_times, 33.33))
        p66 = int(np.percentile(cooking_times, 66.67))

        if p33 >= p66:
            if p66 > min(cooking_times):
                p33 = max(min(cooking_times), p66 - 1)
            else:
                p66 = p33 + 1

        if p33 == p66:
            if p33 == max(cooking_times) and p33 > min(cooking_times):
                p33 = max(min(cooking_times), p33 - 1)
            else:
                p66 = p33 + 1

        CookingTimeRangeFilter._short_threshold = p33
        CookingTimeRangeFilter._medium_threshold = p66

    def lookups(self, request, model_admin):
        self._calculate_thresholds(model_admin.model.objects.all())

        short_t = CookingTimeRangeFilter._short_threshold
        medium_t = CookingTimeRangeFilter._medium_threshold

        return (
            (f'lt_{short_t}', f'Quick (up to {short_t} min)'),
            (f'gte_{short_t}_lte_{medium_t}',
             f'Medium ({short_t}-{medium_t} min)'),
            (f'gt_{medium_t}', f'Long (over {medium_t} min)'),
        )

    def queryset(self, request, queryset):
        self._calculate_thresholds(queryset)

        short_t = CookingTimeRangeFilter._short_threshold
        medium_t = CookingTimeRangeFilter._medium_threshold

        value = self.value()
        if value == f'lt_{short_t}':
            return queryset.filter(cooking_time__lt=short_t)
        if value == f'gte_{short_t}_lte_{medium_t}':
            return queryset.filter(
                cooking_time__gte=short_t,
                cooking_time__lte=medium_t
            )
        if value == f'gt_{medium_t}':
            return queryset.filter(cooking_time__gt=medium_t)
        return queryset


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'measurement_unit',
                    'get_recipe_count_display')
    search_fields = ('name', 'measurement_unit')
    list_filter = ('measurement_unit',)
    empty_value_display = '-пусто-'

    @admin.display(description='Рецепты',
                   ordering='recipes_count')
    def get_recipe_count_display(self, ingredient: Ingredient):
        return ingredient.recipes_count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            recipes_count=Count('recipes'))
        return queryset


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'author', 'cooking_time',  # Added cooking_time
        'get_favorites_count_display',  # Renamed for consistency
        'display_ingredients_short',  # New method for ingredients
        'display_image_thumbnail'  # New method for image
    )
    search_fields = ('name', 'author__username',
                     'author__email')  # Kept existing
    # Changed name filter to custom cooking time filter
    list_filter = ('author', CookingTimeRangeFilter)
    inlines = (RecipeIngredientInline,)
    readonly_fields = ('pub_date', 'get_favorites_count_display',
                       'display_image_preview')
    empty_value_display = '-пусто-'

    # Added ordering
    @admin.display(description='В избранном',
                   ordering='favorites_count_annotation')
    # Renamed obj to recipe
    def get_favorites_count_display(self, recipe: Recipe):
        # Use the annotated value for efficiency
        return recipe.favorites_count_annotation

    @admin.display(description='Ингредиенты')
    @mark_safe
    def display_ingredients_short(self, recipe: Recipe):
        # Access through 'recipeingredients' related_name
        ingredients = recipe.recipeingredients.all()
        if not ingredients:
            return "Нет ингредиентов"
        # Display first 3 ingredients
        display_list = [
            f'{ing.ingredient.name}'
            f' ({ing.amount}'
            f' {ing.ingredient.measurement_unit})' for ing in ingredients]
        return mark_safe("<br>".join(display_list))

    @admin.display(description='Картинка')
    @mark_safe
    def display_image_thumbnail(self, recipe: Recipe):
        if recipe.image and hasattr(recipe.image, 'url'):
            return format_html((
                ' < a href = "{0}" target = "_blank" > <img src = "{0}"'
                ' style = "max-height: 50px; max-width: 70px;" / > < /a > '),
                recipe.image.url
            )
        return "Нет изображения"

    # For readonly_fields, if you want a larger preview there
    @admin.display(description='Картинка')
    @mark_safe
    def display_image_preview(self, recipe: Recipe):
        if recipe.image and hasattr(recipe.image, 'url'):
            return format_html((
                ' < a href = "{0}" target = "_blank" > <img src = "{0}"'
                ' style = "max-height: 200px; max-width: 200px;" / > < /a >'),
                recipe.image.url
            )
            return "Нет изображения"

            def get_queryset(self, request):
                queryset = super().get_queryset(request)
                queryset = queryset.annotate(
                    favorites_count_annotation=Count('favorited_by_set'))
                return queryset


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipe', 'ingredient', 'amount')
    search_fields = ('recipe__name', 'ingredient__name')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')
    search_fields = ('user__username', 'recipe__name')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')
    search_fields = ('user__username', 'recipe__name')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'author')
    search_fields = ('user__username', 'author__username')
