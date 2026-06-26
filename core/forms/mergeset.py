"""Forms related to mergeset setup flows."""

from django import forms

from core.models import Mergeset


class MergesetForm(forms.ModelForm):
    """Basic form boundary for future mergeset creation workflows."""

    description = forms.CharField(
        label="Context",
        required=False,
        help_text="This is sent to the AI at the start of each planning turn.",
        widget=forms.Textarea(
            attrs={
                "placeholder": (
                    "Example: These are UK bank exports. Keep all available "
                    "columns, normalize dates, and preserve source filenames."
                ),
                "rows": 6,
            }
        ),
    )

    class Meta:
        """Configure model-backed form fields."""

        model = Mergeset
        fields = ["name", "description"]
