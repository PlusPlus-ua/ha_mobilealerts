"""Constants for the MobileAlerts integration."""

from homeassistant.backports.enum import StrEnum
from typing import Final

from .mobilealerts import MeasurementType

DOMAIN: Final = "mobile_alerts"

GATEWAY_DEF_NAME: Final = "MOBILEALERTS-Gateway"
MANUFACTURER: Final = "La Crosse Tech. / TFA Dostmann"

CONF_GATEWAY: Final = "gateway_id"
CONF_SEND_DATA_TO_CLOUD: Final = "send_data_to_cloud"

STATE_ATTR_BY_EVENT: Final = "by_event"
STATE_ATTR_ERROR: Final = "error"
STATE_ATTR_LAST_UPDATE: Final = "last_update"
STATE_ATTR_PRIOR_VALUE: Final = "prior_value"
STATE_ATTR_RESTORED: Final = "restored"

STATE_ATTR_EXTRA: set[str] = {
    STATE_ATTR_BY_EVENT,
    STATE_ATTR_ERROR,
    STATE_ATTR_LAST_UPDATE,
    STATE_ATTR_PRIOR_VALUE,
}

class MobileAlertsDeviceClass(StrEnum):
    """MobileAlerts specific device classes, used for translations."""

    KEY_PRESSED = "mobile_alerts__key_pressed"
    KEY_PRESS_TYPE = "mobile_alerts__key_press_type"

BINARY_MAEASUREMENT_TYPES: set[MeasurementType] = {
    MeasurementType.WETNESS,
    MeasurementType.ALARM,
    MeasurementType.DOOR_WINDOW,
}




