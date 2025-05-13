# backend/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.utils.html import format_html, mark_safe
from .models import User

# Custom filters


class HasRecipesFilter(admin.SimpleListFilter):
    title = 'наличие рецептов'
    parameter_name = 'has_recipes'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Есть рецепты'),
            ('no', 'Нет рецептов'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(recipes__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(recipes__isnull=True).distinct()
        return queryset


class HasSubscriptionsFilter(admin.SimpleListFilter):
    title = 'наличие подписок (на кого-то)'
    parameter_name = 'has_following'

    def lookups(self, request, model_admin):
        return (('yes', 'Подписан'), ('no', 'Не подписан'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(followers__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(followers__isnull=True).distinct()
        return queryset


class HasFollowersFilter(admin.SimpleListFilter):  # User has followers
    title = 'наличие подписчиков (на него)'
    parameter_name = 'has_followers_on_self'

    def lookups(self, request, model_admin):
        return (('yes', 'Есть подписчики'), ('no', 'Нет подписчиков'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(authors__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(authors__isnull=True).distinct()
        return queryset


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'id', 'username', 'email', 'get_full_name_display',
        'display_avatar_thumbnail',
        'get_recipe_count_display', 'get_following_count_display',
        'get_follower_count_display',
        'is_staff'
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', HasRecipesFilter,
                   HasSubscriptionsFilter, HasFollowersFilter)
    empty_value_display = '-пусто-'

    # Keep default fieldsets and add avatar
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('avatar',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('first_name', 'last_name', 'avatar')}),
    )

    @admin.display(description='ФИО')
    def get_full_name_display(self, user: User):
        full_name = user.get_full_name()
        return full_name if full_name else user.username

    @admin.display(description='Аватар')
    @mark_safe
    def display_avatar_thumbnail(self, user: User):
        if user.avatar and hasattr(user.avatar, 'url'):
            return format_html(
                '''<img src="{}" style="max-height: 40px; max-width: 40px;
                 border-radius: 50%;" />''',
                user.avatar.url
            )
        return "Нет аватара"

    @admin.display(description='Рецепты', ordering='recipe_count_annotation')
    def get_recipe_count_display(self, user: User):
        return user.recipe_count_annotation

    @admin.display(description='Подписки (на)',
                   ordering='following_count_annotation')
    def get_following_count_display(self, user: User):
        return user.following_count_annotation

    @admin.display(description='Подписчики (его)',
                   ordering='follower_count_annotation')
    def get_follower_count_display(self, user: User):
        return user.follower_count_annotation

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            # Assumes User.recipes is correct related_name
            recipe_count_annotation=Count('recipes', distinct=True),
            # User.followers -> Subscriptions by this user
            following_count_annotation=Count('followers', distinct=True),
            # User.authors -> Subscriptions to this user
            follower_count_annotation=Count('authors', distinct=True)
        )
        return queryset
