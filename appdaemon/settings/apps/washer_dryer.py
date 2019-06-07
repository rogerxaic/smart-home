"""Define automations for washer/dryer appliances."""
from datetime import timedelta
from enum import Enum
from typing import Union

import voluptuous as vol

from const import CONF_NOTIFICATION_INTERVAL, CONF_ENTITY_IDS, CONF_PROPERTIES
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_POWER = "power"
CONF_STATUS = "status"
CONF_CLEAN_THRESHOLD = "clean_threshold"
CONF_DRYING_THRESHOLD = "drying_threshold"
CONF_IOS_EMPTIED_KEY = "ios_emptied_key"
CONF_RUNNING_THRESHOLD = "running_threshold"

HANDLE_CLEAN = "clean"


class NotifyDone(Base):
    """Define a feature to notify a target when the appliancer is done."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_CLEAN_THRESHOLD): float,
                    vol.Required(CONF_DRYING_THRESHOLD): float,
                    vol.Required(CONF_IOS_EMPTIED_KEY): str,
                    vol.Required(CONF_NOTIFICATION_INTERVAL): int,
                    vol.Required(CONF_RUNNING_THRESHOLD): float,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.power_changed,
            self.app.entity_ids[CONF_POWER],
            constrain_input_boolean=self.enabled_entity_id,
        )
        self.listen_state(
            self.status_changed,
            self.app.entity_ids[CONF_STATUS],
            constrain_input_boolean=self.enabled_entity_id,
        )

    def power_changed(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deal with changes to the power draw."""
        power = float(new)
        if (
            self.app.state != self.app.States.running
            and power >= self.properties[CONF_RUNNING_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Running"')

            self.app.state = self.app.States.running
        elif (
            self.app.state == self.app.States.running
            and power <= self.properties[CONF_DRYING_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Drying"')

            self.app.state = self.app.States.drying
        elif (
            self.app.state == self.app.States.drying
            and power == self.properties[CONF_CLEAN_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Clean"')

            self.app.state = self.app.States.clean

    def status_changed(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deal with changes to the status."""
        if new == self.app.States.clean.value:
            self.handles[HANDLE_CLEAN] = send_notification(
                self,
                "presence:home",
                "Empty it now and you won't have to do it later!",
                title="Dishwasher Clean 🍽",
                when=self.datetime() + timedelta(minutes=15),
                interval=self.properties[CONF_NOTIFICATION_INTERVAL],
                data={"push": {"category": "dishwasher"}},
            )
        elif old == self.app.States.clean.value:
            if HANDLE_CLEAN in self.handles:
                cancel = self.handles.pop(HANDLE_CLEAN)
                cancel()


class WasherDryer(Base):  # pylint: disable=too-few-public-methods
    """Define an app to represent a washer/dryer-type appliance."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_POWER): cv.entity_id,
                    vol.Required(CONF_STATUS): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    class States(Enum):
        """Define an enum for states."""

        clean = "Clean"
        dirty = "Dirty"
        drying = "Drying"
        running = "Running"

    @property
    def state(self) -> "States":
        """Get the state."""
        return self.States(self.get_state(self.entity_ids[CONF_STATUS]))

    @state.setter
    def state(self, value: "States") -> None:
        """Set the state."""
        self.select_option(self.entity_ids[CONF_STATUS], value.value)
