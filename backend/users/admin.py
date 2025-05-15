# backend/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.utils.html import mark_safe
from .models import User


class BaseHasFilter(admin.SimpleListFilter):
    """
    Base class for simple list filters that check for the existence
    of related objects.
    Subclasses must define:
    - title (str): The title of the filter.
    - parameter_name (str): The GET parameter name.
    - related_field_name (str): The name of the related field to check for
    null.
    - lookups_tuple (tuple): The tuple for the lookups method.
    """
    lookups_tuple = (
        ('yes', 'Есть'),
        ('no', 'Нет'),
    )  # can be overridden

    def lookups(self, request, model_admin):
        return self.lookups_tuple

    def queryset(self, request, queryset):
        if not hasattr(self, 'related_field_name'):
            raise NotImplementedError(
                "Subclasses of BaseHasFilter must define 'related_field_name'."
            )
        if self.value() == 'yes':
            filter_kwargs = {f'{self.related_field_name}__isnull': False}
            return queryset.filter(**filter_kwargs).distinct()
        if self.value() == 'no':
            filter_kwargs = {f'{self.related_field_name}__isnull': True}
            return queryset.filter(**filter_kwargs).distinct()
        return queryset


class HasRecipesFilter(BaseHasFilter):
    title = 'наличие рецептов'
    parameter_name = 'has_recipes'
    related_field_name = 'recipes'
    lookups_tuple = (
        ('yes', 'Есть рецепты'),
        ('no', 'Нет рецептов'),
    )


class HasSubscriptionsFilter(BaseHasFilter):
    title = 'наличие подписок (на кого-то)'
    parameter_name = 'has_following'
    related_field_name = 'followers'
    lookups_tuple = (
        ('yes', 'Подписан'),
        ('no', 'Не подписан')
    )


class HasFollowersFilter(BaseHasFilter):
    title = 'наличие подписчиков (на него)'
    parameter_name = 'has_followers_on_self'
    related_field_name = 'authors'
    lookups_tuple = (
        ('yes', 'Есть подписчики'),
        ('no', 'Нет подписчиков')
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'id', 'username', 'email', 'get_full_name_display',
        'display_avatar_thumbnail',
        'get_recipe_count', 'get_following_count',
        'get_follower_count',
        'is_staff'
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', HasRecipesFilter,
                   HasSubscriptionsFilter, HasFollowersFilter)
    empty_value_display = '-пусто-'

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('avatar',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('first_name', 'last_name', 'avatar')}),
    )

    @admin.display(description='ФИО')
    def get_full_name_display(self, user: User):
        return user.get_full_name() or user.username

    @admin.display(description='Аватар')
    def display_avatar_thumbnail(self, user: User):
        if user.avatar and hasattr(user.avatar, 'url'):
            html_string = (
                f'<img src="{user.avatar.url}" '
                'style="max-height: 40px; max-width: 40px; '
                'border-radius: 50%;" />'
            )
            return mark_safe(html_string)
        return "Нет аватара"

    @admin.display(description='Рецепты', ordering='recipe_count')
    def get_recipe_count(self, user: User):
        return user.recipe_count

    @admin.display(description='Подписки (на)',
                   ordering='following_count')
    def get_following_count(self, user: User):
        return user.following_count

    @admin.display(description='Подписчики (его)',
                   ordering='follower_count')
    def get_follower_count(self, user: User):
        return user.follower_count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            recipe_count=Count('recipes', distinct=True),
            following_count=Count('followers', distinct=True),
            follower_count=Count('authors', distinct=True)
        )
        return queryset
