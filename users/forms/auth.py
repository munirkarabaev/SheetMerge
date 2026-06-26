"""Forms for the custom user model."""

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from users.models import User


class CustomUserCreationForm(forms.ModelForm):
    """Admin form for creating users."""

    password1 = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", strip=False, widget=forms.PasswordInput)

    class Meta:
        """Define the model backing the form."""

        model = User
        fields = ("email",)

    def clean_password2(self) -> str:
        """Validate that both password entries match."""

        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields did not match.")
        return password2

    def save(self, commit: bool = True) -> User:
        """Hash the password before persisting the user."""

        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """Admin form for updating users."""

    password = ReadOnlyPasswordHashField()

    class Meta:
        """Define the model backing the form."""

        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "ai_token_credit_balance",
            "is_active",
            "is_staff",
            "is_superuser",
        )

    def clean_password(self) -> str:
        """Always return the initial password hash."""

        return self.initial["password"]
