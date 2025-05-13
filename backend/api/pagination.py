# backend/api/pagination.py
from rest_framework.pagination import PageNumberPagination


class FoodgramPageNumberPagination(PageNumberPagination):
    page_size = 6  # Default page size
    # Allow client to override page size via 'limit' query param
    page_size_query_param = 'limit'
    max_page_size = 100  # Optional: Set a maximum page size
