"""Monthly infrastructure estimates in INR, separate from procurement reference prices."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Estimate:
    upfront: float
    operating: float
    monthly: float
    missing: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class OwnedInputs:
    nodes: int
    capex_lines: tuple[tuple[str, float | None], ...]
    kw_per_node: float
    tariff: float
    cooling: float
    months: int
    hours: int
    recurring: tuple[tuple[str, float | None], ...]

    def estimate(self) -> Estimate:
        parts = self.capex_lines
        upfront = self.nodes * sum(value for _, value in parts if value is not None)
        operating = self.nodes * self.kw_per_node * self.hours * self.tariff * self.cooling
        operating += sum(value for _, value in self.recurring if value is not None)
        missing = tuple(name for name, value in (*parts, *self.recurring) if value is None)
        return Estimate(upfront, operating, upfront / self.months + operating, missing)


def rental_estimate(rate_inr: float, nodes: int, hours: int,
                    recurring: tuple[tuple[str, float | None], ...]) -> Estimate:
    monthly = rate_inr * nodes * hours
    monthly += sum(value for _, value in recurring if value is not None)
    return Estimate(0.0, monthly, monthly, tuple(n for n, v in recurring if v is None))
