from django.db import models

from utils.xss_filter import XSSHtml

JSONField = models.JSONField

class RichTextField(models.TextField):
    def get_prep_value(self, value):
        with XSSHtml() as parser:
            return parser.clean(value or "")
