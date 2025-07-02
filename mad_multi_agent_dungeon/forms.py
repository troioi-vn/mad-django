from django import forms
from .models import Agent

class SendCommandForm(forms.Form):
    command = forms.CharField(widget=forms.TextInput(attrs={'size': '80'}))
