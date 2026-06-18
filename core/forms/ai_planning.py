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


class MergePlanRevisionForm(forms.Form):
    """Validate one requested edit to an AI-generated merge plan."""

    instruction = forms.CharField(
        label="Ask AI to revise",
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "id": "mapping-revision",
                "placeholder": "Example: Sort the preview by Date from oldest to newest.",
                "rows": 3,
            }
        ),
    )
