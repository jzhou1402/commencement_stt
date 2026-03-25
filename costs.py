"""Track API costs per pipeline run."""

# Pricing as of March 2026
GROQ_WHISPER_PER_HOUR = 0.111  # $/hour of audio

GPT4O_INPUT_PER_1M = 2.50     # $/1M input tokens
GPT4O_OUTPUT_PER_1M = 10.00   # $/1M output tokens


class CostTracker:
    def __init__(self):
        self.groq_audio_seconds = 0
        self.openai_input_tokens = 0
        self.openai_output_tokens = 0
        self.openai_calls = 0

    def add_groq_audio(self, seconds):
        self.groq_audio_seconds += seconds

    def add_openai_usage(self, response):
        """Extract token usage from an OpenAI chat completion response."""
        if hasattr(response, "usage") and response.usage:
            self.openai_input_tokens += response.usage.prompt_tokens or 0
            self.openai_output_tokens += response.usage.completion_tokens or 0
        self.openai_calls += 1

    @property
    def groq_cost(self):
        hours = self.groq_audio_seconds / 3600
        return hours * GROQ_WHISPER_PER_HOUR

    @property
    def openai_cost(self):
        input_cost = (self.openai_input_tokens / 1_000_000) * GPT4O_INPUT_PER_1M
        output_cost = (self.openai_output_tokens / 1_000_000) * GPT4O_OUTPUT_PER_1M
        return input_cost + output_cost

    @property
    def total_cost(self):
        return self.groq_cost + self.openai_cost

    def summary(self):
        return {
            "groq": {
                "audio_seconds": round(self.groq_audio_seconds, 1),
                "audio_minutes": round(self.groq_audio_seconds / 60, 1),
                "cost": round(self.groq_cost, 4),
            },
            "openai": {
                "calls": self.openai_calls,
                "input_tokens": self.openai_input_tokens,
                "output_tokens": self.openai_output_tokens,
                "cost": round(self.openai_cost, 4),
            },
            "total_cost": round(self.total_cost, 4),
        }
