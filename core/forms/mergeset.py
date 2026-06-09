"""Forms related to mergeset setup flows."""

from django import forms

from core.models import Mergeset


class MergesetForm(forms.ModelForm):
    """Basic form boundary for future mergeset creation workflows."""

    class Meta:
        """Configure model-backed form fields."""

        model = Mergeset
        fields = ["name", "description"]
