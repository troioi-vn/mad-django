from django.db import models


class Agent(models.Model):
    name = models.CharField(max_length=255, unique=True)
    look = models.CharField(max_length=255)
    description = models.TextField()
    flags = models.JSONField(default=dict, blank=True, null=True)
    inventory = models.JSONField(default=list, blank=True, null=True)
    tokens = models.IntegerField(default=0)
    level = models.IntegerField(default=0)
    location = models.CharField(max_length=255, default="start_room")
    last_command_sent = models.DateTimeField(null=True, blank=True)
    last_retrieved = models.DateTimeField(null=True, blank=True)

    PHASE_CHOICES = [
        ("thinking", "Thinking"),
        ("acting", "Acting"),
        ("prompting", "Prompting"),
        ("idle", "Idle"),  # Default phase
    ]
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="idle")
    prompt = models.TextField(blank=True, null=True)
    perception = models.TextField(blank=True, null=True)
    memoriesLoaded = models.JSONField(default=list, blank=True, null=True)
    is_running = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def is_active(self):
        if self.last_command_sent:
            from django.utils import timezone

            return (
                timezone.now() - self.last_command_sent
            ).total_seconds() < 300  # 5 minutes * 60 seconds
        return False


class ObjectInstance(models.Model):
    object_id = models.CharField(max_length=255)
    room_id = models.CharField(max_length=255)
    data = models.JSONField()

    def __str__(self):
        return f"{self.object_id} in {self.room_id}"


class CommandQueue(models.Model):
    command = models.CharField(max_length=1024)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    date = models.DateTimeField(auto_now_add=True)
    output = models.TextField(blank=True)

    def __str__(self):
        return f"{self.command} for {self.agent.name} - {self.status}"


class PerceptionQueue(models.Model):
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="perceptions_for"
    )
    source_agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="perceptions_from",
    )
    TYPE_CHOICES = [
        ("command", "Command"),
        ("none", "None"),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="none")
    command = models.ForeignKey(
        CommandQueue, on_delete=models.CASCADE, null=True, blank=True
    )
    text = models.TextField()
    delivered = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Perception for {self.agent.name} - {self.type}"


class Memory(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="memories")
    key = models.CharField(max_length=255)
    value = models.TextField()

    class Meta:
        unique_together = ("agent", "key")  # Ensure unique key per agent

    def __str__(self):
        return f"Memory for {self.agent.name}: {self.key}"


class LLMQueue(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    prompt = models.TextField()
    yield_value = models.IntegerField(default=0)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("thinking", "Thinking"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("delivered", "Delivered"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    response = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"LLM Prompt for {self.agent.name} - {self.status}"


class LLMAPIKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True)
    usage_count = models.IntegerField(default=0)
    parameters = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return f"API Key: {self.key[:10]}... (Active: {self.is_active})"
