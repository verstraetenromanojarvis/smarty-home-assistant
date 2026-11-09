"""SMARTY sensors: site energy balance plus per-device telemetry.

Sign conventions are SMARTY's:
  battery power  > 0 = discharging, < 0 = charging
  grid power     > 0 = importing,   < 0 = exporting
Separate always-positive import/export and charge/discharge sensors are added
because Home Assistant's energy/power cards expect those.

Costs are SMARTY's own result with the sign flipped: > 0 = paid, < 0 = earned.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import SmartyConfigEntry
from .const import DOMAIN

# SMARTY strategy keys (site.ems_mode); anything else is shown as unknown.
STRATEGY_OPTIONS = [
    "self_consumption",
    "cost_minimization",
    "peak_shaving",
    "time_of_use",
    "grid_export",
    "manual",
    "off",
]
BATTERY_STATUS_OPTIONS = ["charging", "discharging", "standby", "sleep", "fault"]
# Added in 1.2.0: backup (EPS) power during a grid outage.
GRID_MODE_OPTIONS = ["on_grid", "backup"]
INVERTER_STATE_OPTIONS = ["wait", "normal", "fault"]
BACKUP_ACTIVE_OPTIONS = ["on", "off"]


@dataclass(frozen=True, kw_only=True)
class SiteSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    last_reset_fn: Callable[[dict], datetime | None] | None = None
    attributes_fn: Callable[[dict], dict[str, Any] | None] | None = None


def _power(key: str, transform: Callable[[float], float] = lambda v: v) -> Callable[[dict], Any]:
    def value(data: dict) -> Any:
        raw = (data.get("power") or {}).get(key)
        return None if raw is None else round(transform(float(raw)), 1)
    return value


def _power_description(key: str, value_fn: Callable[[dict], Any]) -> SiteSensorDescription:
    return SiteSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=value_fn,
    )


def _option(value: Any, options: list[str]) -> str | None:
    # An ENUM sensor must never report a state outside its options.
    return value if isinstance(value, str) and value in options else None


def _backup_active(data: dict) -> str | None:
    # True/False from SMARTY; None (no fresh inverter reports it) stays unknown.
    value = data.get("backup_active")
    if value is True:
        return "on"
    if value is False:
        return "off"
    return None


def _finance(data: dict) -> dict:
    block = data.get("finance")
    return block if isinstance(block, dict) else {}


def _period(period: str) -> Callable[[dict], dict]:
    def block(data: dict) -> dict:
        value = _finance(data).get(period)
        return value if isinstance(value, dict) else {}
    return block


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cost_description(key: str, period: str) -> SiteSensorDescription:
    block = _period(period)
    return SiteSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.MONETARY,
        # MONETARY only allows TOTAL. The value resets each day/month and can
        # go down (export earns money), so TOTAL_INCREASING would be wrong;
        # last_reset tells Home Assistant's statistics where a new period starts.
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda data: _number(block(data).get("cost_eur")),
        last_reset_fn=lambda data: dt_util.parse_datetime(str(block(data).get("since") or "")),
        attributes_fn=lambda data: {"status": block(data).get("status")},
    )


SITE_SENSORS: tuple[SiteSensorDescription, ...] = (
    _power_description("solar_power", _power("solar_w")),
    _power_description("grid_power", _power("grid_w")),
    _power_description("grid_import_power", _power("grid_w", lambda v: max(v, 0.0))),
    _power_description("grid_export_power", _power("grid_w", lambda v: max(-v, 0.0))),
    _power_description("battery_power", _power("battery_w")),
    _power_description("battery_charge_power", _power("battery_w", lambda v: max(-v, 0.0))),
    _power_description("battery_discharge_power", _power("battery_w", lambda v: max(v, 0.0))),
    _power_description("home_power", _power("home_w")),
    _power_description("ev_power", _power("ev_w")),
    _power_description("heat_pump_power", _power("heatpump_w")),
    SiteSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.get("battery_soc_pct"),
    ),
    SiteSensorDescription(
        key="data_status",
        translation_key="data_status",
        device_class=SensorDeviceClass.ENUM,
        options=["ok", "partial", "stale", "no_devices"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status"),
    ),
    # Added in 1.1.0 (SMARTY payload schema 1.1; absent keys → unavailable).
    SiteSensorDescription(
        key="strategy",
        translation_key="strategy",
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_OPTIONS,
        value_fn=lambda data: _option(data.get("ems_mode"), STRATEGY_OPTIONS),
    ),
    _cost_description("cost_today", "today"),
    _cost_description("cost_month", "month"),
    SiteSensorDescription(
        key="self_consumption",
        translation_key="self_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda data: _number(_finance(data).get("self_consumption_pct")),
    ),
    # Added in 1.2.0 (SMARTY payload schema 1.2): "on" while any inverter of
    # the site feeds the house from its backup output (grid gone).
    SiteSensorDescription(
        key="backup_active",
        translation_key="backup_active",
        device_class=SensorDeviceClass.ENUM,
        options=BACKUP_ACTIVE_OPTIONS,
        value_fn=_backup_active,
    ),
)

_ENERGY_TOTAL = dict(
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
)
_ENERGY_STORED = dict(
    device_class=SensorDeviceClass.ENERGY_STORAGE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
)
_POWER = dict(
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
)
_TEMP = dict(
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)

# Mirrors services/home_assistant.py DEVICE_FIELDS (+ DERIVED_DEVICE_FIELDS)
# on the SMARTY side.
DEVICE_FIELD_SENSORS: dict[str, dict[str, Any]] = {
    "ac_power_w": _POWER,
    "pv_power_w": _POWER,
    "battery_power_w": _POWER,
    "net_power_w": _POWER,
    "ev_power_w": _POWER,
    "heat_pump_power_w": _POWER,
    "load_power_w": _POWER,
    "heat_output_w": _POWER,
    "battery_soc_pct": dict(
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    # Daily counters reset at midnight; TOTAL_INCREASING treats that as a new cycle.
    "daily_energy_kwh": _ENERGY_TOTAL,
    "total_energy_kwh": _ENERGY_TOTAL,
    "grid_import_today_kwh": _ENERGY_TOTAL,
    "grid_export_today_kwh": _ENERGY_TOTAL,
    "grid_import_total_kwh": _ENERGY_TOTAL,
    "grid_export_total_kwh": _ENERGY_TOTAL,
    "grid_voltage_v": dict(
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "grid_frequency_hz": dict(
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    "grid_current_a": dict(
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "inverter_temp_c": _TEMP,
    "battery_temp_c": _TEMP,
    "water_temp_c": _TEMP,
    "flow_temp_c": _TEMP,
    "return_temp_c": _TEMP,
    "dhw_temp_c": _TEMP,
    "outdoor_temp_c": _TEMP,
    "room_temp_c": _TEMP,
    "cop": dict(state_class=SensorStateClass.MEASUREMENT),
    # Added in 1.1.0. Lifetime battery counters for the Energy dashboard.
    "battery_charge_total_kwh": _ENERGY_TOTAL,
    "battery_discharge_total_kwh": _ENERGY_TOTAL,
    "battery_cycle_count": dict(
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    "battery_soh_pct": dict(
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "battery_voltage_v": dict(
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "battery_current_a": dict(
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "battery_capacity_kwh": _ENERGY_STORED,
    "battery_energy_remaining_kwh": _ENERGY_STORED,
    # Added in 1.2.0: backup (EPS) output of an inverter during a grid outage.
    "eps_power_w": _POWER,
    "eps_voltage_v": dict(
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "eps_frequency_hz": dict(
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    "eps_output_total_kwh": _ENERGY_TOTAL,
}

# Text states per device (payload ``states``; raw SMARTY keys, translated here).
DEVICE_STATE_SENSORS: dict[str, dict[str, Any]] = {
    "battery_status": dict(device_class=SensorDeviceClass.ENUM, options=BATTERY_STATUS_OPTIONS),
    # Added in 1.2.0.
    "grid_mode": dict(device_class=SensorDeviceClass.ENUM, options=GRID_MODE_OPTIONS),
    "inverter_state": dict(device_class=SensorDeviceClass.ENUM, options=INVERTER_STATE_OPTIONS),
}

# ── Cumulative counters ───────────────────────────────────────────────────────
# Home Assistant counts any drop of a total_increasing sensor below 90 % of
# the previous value as a meter reset. A single corrupt sample (dip, or an
# impossible jump and back) would then add the whole counter to the Energy
# dashboard again. Such a sample is held back (sensor briefly unavailable); a
# new level that persists for COUNTER_CONFIRM_SAMPLES polls in a row is real
# (daily counter reset at midnight, replaced meter).
COUNTER_CONFIRM_SAMPLES = 3
COUNTER_MAX_RATE_PER_H = 1000.0  # 1 MW for kWh counters: far above any site
COUNTER_SLACK = 1.0
COUNTER_DIP_TOLERANCE = 0.001


class CounterFilter:
    def __init__(self) -> None:
        self._value: float | None = None
        self._at: datetime | None = None
        self._held = 0

    def __call__(self, value: Any, now: datetime) -> float | None:
        value = _number(value)
        if value is None:
            return None
        if self._value is not None and self._at is not None:
            hours = max((now - self._at).total_seconds(), 0.0) / 3600
            ceiling = self._value + COUNTER_SLACK + COUNTER_MAX_RATE_PER_H * hours
            if not self._value - COUNTER_DIP_TOLERANCE <= value <= ceiling:
                self._held += 1
                if self._held < COUNTER_CONFIRM_SAMPLES:
                    return None
        self._value, self._at, self._held = value, now, 0
        return value


def _site_device_info(data: dict) -> DeviceInfo:
    site = data["site"]
    return DeviceInfo(
        identifiers={(DOMAIN, f"site_{site['id']}")},
        name=site.get("name") or "SMARTY",
        manufacturer="SMARTY",
        model="Energiebeheer",
    )


def _device_info(device: dict, site_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"device_{device['id']}")},
        name=device.get("name") or device.get("brand") or "Apparaat",
        manufacturer=device.get("brand"),
        model=device.get("model"),
        via_device=(DOMAIN, f"site_{site_id}"),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    site_id = str(coordinator.data["site"]["id"])
    async_add_entities(SmartySiteSensor(coordinator, site_id, description) for description in SITE_SENSORS)

    known: set[tuple[str, str]] = set()

    @callback
    def _add_device_sensors() -> None:
        new = []
        for device in (coordinator.data or {}).get("devices") or []:
            for source, catalog in (("fields", DEVICE_FIELD_SENSORS), ("states", DEVICE_STATE_SENSORS)):
                values = device.get(source)
                for field in values if isinstance(values, dict) else {}:
                    if field not in catalog or (device["id"], field) in known:
                        continue
                    known.add((device["id"], field))
                    new.append(SmartyDeviceSensor(coordinator, site_id, device, field, source))
        if new:
            async_add_entities(new)

    _add_device_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_device_sensors))


class SmartySiteSensor(CoordinatorEntity[DataUpdateCoordinator[dict]], SensorEntity):
    _attr_has_entity_name = True
    entity_description: SiteSensorDescription

    def __init__(self, coordinator, site_id: str, description: SiteSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{site_id}_{description.key}"
        self._attr_device_info = _site_device_info(coordinator.data)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def last_reset(self) -> datetime | None:
        last_reset_fn = self.entity_description.last_reset_fn
        return last_reset_fn(self.coordinator.data or {}) if last_reset_fn else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes_fn = self.entity_description.attributes_fn
        return attributes_fn(self.coordinator.data or {}) if attributes_fn else None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.entity_description.key == "data_status" or self.native_value is not None


class SmartyDeviceSensor(CoordinatorEntity[DataUpdateCoordinator[dict]], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, site_id: str, device: dict, field: str, source: str = "fields") -> None:
        super().__init__(coordinator)
        self._device_id = str(device["id"])
        self._field = field
        self._source = source
        # Unchanged since 1.0.0: renaming would orphan existing entities.
        self._attr_unique_id = f"{self._device_id}_{field}"
        self._attr_translation_key = field
        self._attr_device_info = _device_info(device, site_id)
        catalog = DEVICE_STATE_SENSORS if source == "states" else DEVICE_FIELD_SENSORS
        for attribute, value in catalog[field].items():
            setattr(self, f"_attr_{attribute}", value)
        is_counter = catalog[field].get("state_class") == SensorStateClass.TOTAL_INCREASING
        self._counter = CounterFilter() if is_counter else None
        self._attr_native_value = self._read()

    def _device(self) -> dict | None:
        for device in (self.coordinator.data or {}).get("devices") or []:
            if str(device.get("id")) == self._device_id:
                return device
        return None

    def _read(self) -> Any:
        device = self._device()
        # Stale telemetry is shown as unavailable rather than as a current value.
        if device is None or device.get("status") != "ok":
            return None
        values = device.get(self._source)
        value = values.get(self._field) if isinstance(values, dict) else None
        if self._source == "states":
            return _option(value, self._attr_options)
        if self._counter is not None:
            return self._counter(value, dt_util.utcnow())
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        # Once per poll (not per property read): the counter filter is stateful.
        self._attr_native_value = self._read()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> Any:
        return self._attr_native_value

    @property
    def available(self) -> bool:
        return super().available and self._attr_native_value is not None
