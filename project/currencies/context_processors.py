from currencies.services import get_currency_by_language


class LazyObject:
    def __init__(self, initial_func, *args, **kwargs):
        self.initial_func = initial_func
        self.args = args
        self.kwargs = kwargs
        self._wrapped = None

    def __getattr__(self, item):
        if self._wrapped is None:
            self._wrapped = self.initial_func(*self.args, **self.kwargs)
        return getattr(self._wrapped, item)


def local_currency_processor(request):
    language = request.LANGUAGE_CODE
    return {
        "LOCAL_CURRENCY": LazyObject(get_currency_by_language, language)
    }
