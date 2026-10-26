from django import forms

from accounts.forms import BootstrapMixin
from accounts.privacy import contains_contact_details
from .models import Complaint, Review


class ComplaintForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["category", "description", "evidence_reference"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class ComplaintResponseForm(BootstrapMixin, forms.Form):
    response = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}), label="Your response")


class ReviewForm(BootstrapMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(i, f"{i} / 5") for i in range(5, 0, -1)], coerce=int)

    class Meta:
        model = Review
        fields = ["rating", "reason_code", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}

    def clean_comment(self):
        c = self.cleaned_data["comment"]
        if contains_contact_details(c):
            raise forms.ValidationError("Please remove phone numbers or emails from your comment.")
        return c
