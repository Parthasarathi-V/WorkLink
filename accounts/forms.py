from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.conf import settings
from django.db import transaction

from .constants import JOB_TYPE_CHOICES
from .models import BusinessProfile, VerificationSubmission, WorkerProfile


class BootstrapMixin:
    """Adds Bootstrap classes to widgets so forms look right without extra packages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            if isinstance(w, forms.CheckboxInput):
                cls = "form-check-input"
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                cls = "form-select"
            else:
                cls = "form-control"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + cls).strip()


class RegisterForm(BootstrapMixin, UserCreationForm):
    ROLE_CHOICES = [("worker", "I'm looking for part-time work (worker / student)"),
                    ("business", "I'm hiring (local business)")]
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    name = forms.CharField(max_length=150, label="Your name (or business name)")
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False  # admin can never be self-assigned
        user.save()
        name = self.cleaned_data["name"]
        if self.cleaned_data["role"] == "worker":
            WorkerProfile.objects.create(user=user, display_name=name)
        else:
            BusinessProfile.objects.create(user=user, business_name=name)
        return user


class WorkerProfileForm(BootstrapMixin, forms.ModelForm):
    preferred_job_types = forms.MultipleChoiceField(choices=JOB_TYPE_CHOICES, required=False,
                                                    widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = WorkerProfile
        fields = ["display_name", "phone", "education", "skills", "preferred_area", "availability", "preferred_job_types"]
        widgets = {"skills": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["preferred_job_types"] = self.instance.job_type_list()

    def clean_preferred_job_types(self):
        return ",".join(self.cleaned_data["preferred_job_types"])


class BusinessProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ["business_name", "category", "area", "address", "phone", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class VerificationForm(BootstrapMixin, forms.ModelForm):
    ALLOWED = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}

    class Meta:
        model = VerificationSubmission
        fields = ["document_type", "document"]

    def __init__(self, *args, account_type="worker", **kwargs):
        super().__init__(*args, **kwargs)
        D = VerificationSubmission.DocumentType
        allowed = [D.STUDENT_ID, D.OTHER] if account_type == "worker" else [D.BUSINESS_REG, D.OTHER]
        self.fields["document_type"].choices = [(d.value, d.label) for d in allowed]

    def clean_document(self):
        f = self.cleaned_data["document"]
        if f.size > settings.WORKLINK["MAX_UPLOAD_BYTES"]:
            raise forms.ValidationError("File is too large (max 5 MB).")
        ext = "." + f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in self.ALLOWED:
            raise forms.ValidationError("Only PDF, PNG or JPG files are accepted.")
        head = f.read(8)
        f.seek(0)
        if not head.startswith(self.ALLOWED[ext]):  # don't trust the extension alone
            raise forms.ValidationError("File contents do not match its type.")
        return f
