"""Constants for the MobileAlerts integration."""

from typing_extensions import Final

from enum import StrEnum
from mobilealerts import MeasurementType

DOMAIN: Final = "mobile_alerts"

GATEWAY_DEF_NAME: Final = "MOBILEALERTS-Gateway"
MANUFACTURER: Final = "La Crosse Tech. / TFA Dostmann"

CONF_GATEWAY: Final = "gateway_id"
CONF_SEND_DATA_TO_CLOUD: Final = "send_data_to_cloud"

STATE_ATTR_BY_EVENT: Final = "by_event"
STATE_ATTR_ERROR: Final = "error"
STATE_ATTR_LAST_UPDATED: Final = "last_updated"
STATE_ATTR_PRIOR_VALUE: Final = "prior_value"
STATE_ATTR_MEASUREMTS: Final = "measurements"

STATE_ATTR_EXTRA: set[str] = {
    STATE_ATTR_BY_EVENT,
    STATE_ATTR_ERROR,
    STATE_ATTR_LAST_UPDATED,
    STATE_ATTR_PRIOR_VALUE,
    STATE_ATTR_MEASUREMTS,
}

BINARY_MEASUREMENT_TYPES: set[MeasurementType] = {
    MeasurementType.WETNESS,
    MeasurementType.ALARM,
    MeasurementType.DOOR_WINDOW,
}

ENUM_MEASUREMENT_TYPES: set[MeasurementType] = {
    MeasurementType.KEY_PRESSED,
    MeasurementType.KEY_PRESS_TYPE,
}

FLOAT_MEASUREMENT_TYPES: set[MeasurementType] = {
    MeasurementType.TEMPERATURE,
    MeasurementType.HUMIDITY,
    MeasurementType.CO2,
    MeasurementType.AIR_PRESSURE,
    MeasurementType.RAIN,
    MeasurementType.TIME_SPAN,
    MeasurementType.WIND_SPEED,
    MeasurementType.GUST,
    MeasurementType.WIND_DIRECTION,
}

LAST_RAIN_PERIOD = 15.0 * 60.0
