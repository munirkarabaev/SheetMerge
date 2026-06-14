"""Forms for uploading source spreadsheets."""

from pathlib import Path

from django import forms


MAX_UPLOAD_SIZE = 10 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


class MultipleFileInput(forms.ClearableFileInput):
    """Allow one file input to submit multiple source files."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Validate every file submitted through a multiple file input."""

    def clean(self, data, initial=None):
        """Return a list containing each individually validated file."""

        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class MergesetFileUploadForm(forms.Form):
    """Validate CSV and XLSX source files before storage."""

    files = MultipleFileField(
        label="Source files",
        widget=MultipleFileInput(
            attrs={
                "accept": ".csv,.xlsx",
            }
        ),
    )

    def clean_files(self):
        """Reject unsupported extensions and files above the upload limit."""

        files = self.cleaned_data["files"]
        for uploaded_file in files:
            extension = Path(uploaded_file.name).suffix.lower()
            if extension not in SUPPORTED_EXTENSIONS:
                raise forms.ValidationError(
                    f"{uploaded_file.name}: only CSV and XLSX files are supported."
                )
            if uploaded_file.size > MAX_UPLOAD_SIZE:
                raise forms.ValidationError(
                    f"{uploaded_file.name}: files must be 10 MB or smaller."
                )
        return files
