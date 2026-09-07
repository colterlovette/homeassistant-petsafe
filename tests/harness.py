"""Stub just enough of homeassistant + petsafe to import SensorEntities."""
import sys, types, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")
_FROZEN = {"now": None}

def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

# --- homeassistant.util.dt : faithful re-implementations -------------------
def now():
    return _FROZEN["now"] or datetime.datetime.now(TZ)

def as_local(d):
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)          # matches HA 2026.9.0 dt.py:179-180
    return d.astimezone(TZ)

def utc_from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

dt_stub = mod("homeassistant.util.dt", now=now, as_local=as_local,
              utc_from_timestamp=utc_from_timestamp)

mod("homeassistant")
mod("homeassistant.components")
mod("homeassistant.components.sensor", SensorEntity=type("SensorEntity", (), {}))
mod("homeassistant.const", PERCENTAGE="%", SIGNAL_STRENGTH_DECIBELS_MILLIWATT="dBm")
mod("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
mod("homeassistant.helpers")
mod("homeassistant.helpers.entity", DeviceInfo=dict)
mod("homeassistant.helpers.update_coordinator",
    CoordinatorEntity=type("CoordinatorEntity", (), {"__init__": lambda self, c: None}))
util = mod("homeassistant.util"); util.dt = dt_stub

devices = mod("petsafe.devices", DeviceSmartFeed=type("DeviceSmartFeed", (), {}),
              DeviceScoopfree=type("DeviceScoopfree", (), {}))
ps = mod("petsafe"); ps.devices = devices

# Stand in for the integration package so SensorEntities' relative imports
# ("from . import PetSafeCoordinator, PetSafeData") resolve without dragging in
# __init__.py, which needs the real homeassistant package.
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
pkg = mod("petsafe_integration", PetSafeCoordinator=object, PetSafeData=object)
pkg.__path__ = [os.path.join(_HERE, os.pardir, "custom_components", "petsafe")]

# --- extra stubs so helpers.py imports (registry + config_entries) ----------
mod("homeassistant.config_entries", ConfigEntryState=type("ConfigEntryState", (), {"LOADED": "loaded"}))
_dr = mod("homeassistant.helpers.device_registry", async_get=lambda h: None,
          async_entries_for_area=lambda *a: [], DeviceEntry=object, DeviceRegistry=object)
_er = mod("homeassistant.helpers.entity_registry", async_get=lambda h: None,
          async_entries_for_area=lambda *a: [], EntityRegistry=object)
sys.modules["homeassistant.helpers"].device_registry = _dr
sys.modules["homeassistant.helpers"].entity_registry = _er
sys.modules["homeassistant.helpers.entity"].EntityCategory = type("EntityCategory", (), {"CONFIG": "config"})
