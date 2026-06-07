"""Forms related to project setup flows."""

from django import forms

from core.models import Project


class ProjectForm(forms.ModelForm):
    """Basic form boundary for future project creation workflows."""

    class Meta:
        """Configure model-backed form fields."""

        model = Project
        fields = ["name", "description"]
