# backend/api/filters.py
from django_filters.rest_framework import FilterSet, filters
from rest_framework.filters import SearchFilter

from .models import Recipe


class IngredientFilter(SearchFilter):
    search_param = 'name'  # Parameter name expected by frontend


class RecipeFilter(FilterSet):
    """FilterSet for filtering recipes."""
    is_favorited = filters.BooleanFilter(
        method='filter_is_favorited',
        label='В избранном'
    )
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
        label='В списке покупок'
    )

    class Meta:
        model = Recipe
        fields = ('author', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, modelset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return modelset.filter(favorited_by_set__user=user)
        return modelset

    def filter_is_in_shopping_cart(self, modelset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return modelset.filter(in_shopping_cart_set__user=user)
        return modelset
