"""The MobileAlerts integration utilities."""

from homeassistant.core import callback

from mobilealerts import Gateway

from .const import GATEWAY_DEF_NAME


@callback
def gateway_short_name(gateway: Gateway) -> str:
    """Return a short name for the gateway."""
    return gateway.name if gateway.name != GATEWAY_DEF_NAME else gateway.gateway_id


@callback
def gateway_full_name(gateway: Gateway) -> str:
    """Return a full name for the gateway."""
    return (
        f"{gateway.name} ({gateway.gateway_id})"
        if gateway.name != GATEWAY_DEF_NAME
        else f"Gateway ({gateway.gateway_id})"
    )
