from django import forms

from accounts.forms import BootstrapMixin
from .models import Job


class JobForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Job
        fields = ["title", "description", "duties", "job_type", "pay_min", "pay_max", "pay_period",
                  "area", "schedule", "required_skills", "vacancies", "closing_at"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "duties": forms.Textarea(attrs={"rows": 3}),
            "required_skills": forms.Textarea(attrs={"rows": 2}),
            "closing_at": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class JobFilterForm(BootstrapMixin, forms.Form):
    q = forms.CharField(required=False, label="Keyword")
    area = forms.CharField(required=False)
    job_type = forms.ChoiceField(required=False, choices=[("", "Any type")] + list(Job._meta.get_field("job_type").choices))
    min_pay = forms.IntegerField(required=False, min_value=0, label="Min pay (₹)")
    skill = forms.CharField(required=False)
    schedule = forms.CharField(required=False)
    sort = forms.ChoiceField(required=False, choices=[("new", "Newest"), ("match", "Best match")])
