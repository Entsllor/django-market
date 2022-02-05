from rest_framework.response import Response
from rest_framework.reverse import reverse_lazy
from rest_framework.test import APIClient

from market_app.tests.base_case import BaseTestCase, BaseMarketTestCase, TestBaseWithFilledCatalogue

GET = 'get'
POST = 'post'
PUT = 'put'
PATCH = 'patch'
DELETE = 'delete'
OPTION = 'option'
HEAD = 'head'


class BaseApiTestCase(BaseTestCase):
    client_class = APIClient
    app_name = "market-api"
    view_class = None
    model = None

    @property
    def serializer_class(self):
        return self.view_class.serializer_class

    def request(self,
                method: str,
                pk=None,
                url=None,
                data: dict = None,
                expected_code=200,
                expected_redirect: str = None,
                **kwargs
                ) -> Response:
        client_method = getattr(self.client, method.lower())
        if url is None:
            url = self.get_url(pk)
        response = client_method(url, data, **kwargs)
        if expected_redirect:
            self.assertRedirects(response, expected_redirect, target_status_code=expected_code)
        elif expected_code:
            self.assertEqual(response.status_code, expected_code)
        return response

    def get_model_name(self) -> str:
        if not hasattr(self, 'model_name'):
            if self.model:
                self.model_name = self.model.__name__.lower()
            else:
                # In UserView model_name = user
                self.model_name = self.view_class.__name__[:self.view_class.__name__.index("View", 3)].lower()
        return self.model_name

    def get_url(self, pk=None):
        if pk:
            return reverse_lazy(f"{self.app_name}:{self.get_model_name()}-detail", kwargs={"pk": pk})
        else:
            return reverse_lazy(f"{self.app_name}:{self.get_model_name()}-list")


class MarketApiTestCase(BaseApiTestCase, BaseMarketTestCase):
    pass


class MarketApiTestCaseWithFilledCatalogue(APIClient, TestBaseWithFilledCatalogue):
    pass
