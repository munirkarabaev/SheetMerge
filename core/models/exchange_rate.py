"""Exchange-rate cache models."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ExchangeRate(models.Model):
    """Stores one monthly average currency exchange rate."""

    base_currency = models.CharField(max_length=3)
    quote_currency = models.CharField(max_length=3)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    average_rate = models.DecimalField(max_digits=18, decimal_places=8)
    provider = models.CharField(max_length=64)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata."""

        constraints = [
            models.UniqueConstraint(
                fields=["base_currency", "quote_currency", "year", "month"],
                name="unique_monthly_exchange_rate",
            )
        ]
        ordering = ["-year", "-month", "base_currency", "quote_currency"]

    def save(self, *args, **kwargs) -> None:
        """Normalize currency codes before saving."""

        self.base_currency = self.base_currency.upper()
        self.quote_currency = self.quote_currency.upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a readable rate label."""

        rate = self.average_rate.quantize(Decimal("0.00000001"))
        return f"{self.base_currency}/{self.quote_currency} {self.year}-{self.month:02d}: {rate}"
