def current_language_processor(request):
    language = request.LANGUAGE_CODE
    return {
        "CURRENT_LANGUAGE": language
    }
