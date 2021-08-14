from django.views.generic import TemplateView


class AboutUsView(TemplateView):
    template_name = 'core_app/about_us_template.html'
