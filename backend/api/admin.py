# backend/api/admin.py
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html, mark_safe
from .models import (Ingredient, Recipe, RecipeIngredient,
                     Favorite, ShoppingCart, Subscription)

# For RecipeAdmin cooking_time filter


class CookingTimeRangeFilter(admin.SimpleListFilter):
    title = 'время приготовления'
    parameter_name = 'cooking_time_range'

    SHORT_THRESHOLD_MINUTES = 30
    MEDIUM_THRESHOLD_MINUTES = 60

    def lookups(self, request, model_admin):
        return (
            (f'<{self.SHORT_THRESHOLD_MINUTES}',
             f'Быстрые (до {self.SHORT_THRESHOLD_MINUTES} мин)'),
            (f'{self.SHORT_THRESHOLD_MINUTES}-{self.MEDIUM_THRESHOLD_MINUTES}',
             f'''Средние
              ({self.SHORT_THRESHOLD_MINUTES}-{self.MEDIUM_THRESHOLD_MINUTES}
               мин)'''),
            (f'>{self.MEDIUM_THRESHOLD_MINUTES}',
             f'Долгие (более {self.MEDIUM_THRESHOLD_MINUTES} мин)'),
        )

    def queryset(self, request, queryset):
        if self.value() == f'<{self.SHORT_THRESHOLD_MINUTES}':
            return queryset.filter(
                cooking_time__lt=self.SHORT_THRESHOLD_MINUTES)
        if self.value() == f'''
        {self.SHORT_THRESHOLD_MINUTES}-{self.MEDIUM_THRESHOLD_MINUTES}''':
            return queryset.filter(
                cooking_time__gte=self.SHORT_THRESHOLD_MINUTES,
                cooking_time__lte=self.MEDIUM_THRESHOLD_MINUTES)
        if self.value() == f'>{self.MEDIUM_THRESHOLD_MINUTES}':
            return queryset.filter(
                cooking_time__gt=self.MEDIUM_THRESHOLD_MINUTES)
        return queryset


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'measurement_unit',
                    'get_recipe_count_display')
    search_fields = ('name', 'measurement_unit')
    list_filter = ('measurement_unit',)
    empty_value_display = '-пусто-'

    # Use ordering
    @admin.display(description='Кол-во рецептов',
                   ordering='recipes_count_annotation')
    # Renamed obj, added type hint
    def get_recipe_count_display(self, ingredient: Ingredient):
        # Use the pre-annotated value for efficiency
        return ingredient.recipes_count_annotation

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            recipes_count_annotation=Count('recipes_featuring_ingredient'))
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

    @admin.display(description='Ингредиенты (до 3)')
    @mark_safe
    def display_ingredients_short(self, recipe: Recipe):
        # Access through 'recipeingredients' related_name
        ingredients = recipe.recipeingredients.all()
        if not ingredients:
            return "Нет ингредиентов"
        # Display first 3 ingredients
        display_list = [
            f'''{ing.ingredient.name}
             ({ing.amount}
             {ing.ingredient.measurement_unit})''' for ing in ingredients[:3]]
        output = ",<br>".join(display_list)  # Use <br> for new lines in admin
        if len(ingredients) > 3:
            output += ", ..."
        return mark_safe(output)

    @admin.display(description='Картинка (превью)')
    @mark_safe
    def display_image_thumbnail(self, recipe: Recipe):
        if recipe.image and hasattr(recipe.image, 'url'):
            return format_html(
                '''<a href="{0}" target="_blank"><img src="{0}"
                 style="max-height: 50px; max-width: 70px;" /></a>''',
                recipe.image.url
            )
        return "Нет изображения"

    # For readonly_fields, if you want a larger preview there
    @admin.display(description='Картинка (полная)')
    @mark_safe
    def display_image_preview(self, recipe: Recipe):
        if recipe.image and hasattr(recipe.image, 'url'):
            return format_html(
                '''<a href="{0}" target="_blank"><img src="{0}"
                 style="max-height: 200px; max-width: 200px;" /></a>''',
                recipe.image.url
            )
        return "Нет изображения"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Annotate for sorting favorites count
        # Assumes Favorite.recipe.related_name is 'favorited_by_set'
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
