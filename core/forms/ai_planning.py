"""Forms for AI-assisted merge planning."""

from django import forms


class MergePlanningMessageForm(forms.Form):
    """Validate one user message for the AI planning conversation."""

    content = forms.CharField(
        label="Your instructions",
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "id": "ai-instructions",
                "placeholder": (
                    "Example: Merge these into Date, Description, Amount, and "
                    "Source. Combine debit and credit into one signed amount."
                ),
                "rows": 5,
            }
        ),
    )
