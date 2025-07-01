from django import forms
from .models import Agent

class SendCommandForm(forms.Form):
    agent = forms.ModelChoiceField(queryset=Agent.objects.all(), label="Select Agent")
    command = forms.CharField(max_length=255, label="Command")
