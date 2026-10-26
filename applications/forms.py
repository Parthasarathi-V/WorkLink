from django import forms

from accounts.forms import BootstrapMixin
from accounts.privacy import contains_contact_details


class ApplyForm(BootstrapMixin, forms.Form):
    cover_note = forms.CharField(required=False, max_length=1000, label="Short note (optional)",
                                 widget=forms.Textarea(attrs={"rows": 3}))

    def clean_cover_note(self):
        note = self.cleaned_data["cover_note"]
        if contains_contact_details(note):
            raise forms.ValidationError("Please don't share phone numbers or emails. WorkLink coordinators arrange contact.")
        return note


class MessageForm(BootstrapMixin, forms.Form):
    body = forms.CharField(max_length=1000, label="Message", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, enforce_privacy=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.enforce_privacy = enforce_privacy

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if self.enforce_privacy and contains_contact_details(body):
            raise forms.ValidationError(
                "For safety, don't share phone numbers or emails here. A WorkLink coordinator can arrange contact.")
        return body
