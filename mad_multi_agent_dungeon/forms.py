from django import forms


class SendCommandForm(forms.Form):
    command = forms.CharField(widget=forms.TextInput(attrs={"size": "80"}))
