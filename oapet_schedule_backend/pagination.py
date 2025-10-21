# oapet_schedule_backend/pagination.py
from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """
    Pagination personnalisée permettant au client de spécifier la taille de page
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
