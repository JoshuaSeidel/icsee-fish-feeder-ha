# iCSee Feeder Home Assistant Integration

This custom integration controls iCSee/XMEye fish and pet feeders over the local DVRIP/Sofia TCP protocol. It does not use the iCSee cloud account.

## Features

- UI setup flow for host, port, username, password, and default servings.
- `button.feed` entity for a one-tap manual feeding.
- `number.portions` entity that controls how many servings the button dispenses.
- `icsee_feeder.feed` entity service for automations with an optional `servings` override.
- Sensors for latest feed timestamp, latest feed servings, schedule count, and advertised feeder support.

## Install

Copy `custom_components/icsee_feeder` into your Home Assistant config directory:

```text
<ha config>/custom_components/icsee_feeder
```

Restart Home Assistant, then add the integration from:

```text
Settings -> Devices & services -> Add integration -> iCSee Feeder
```

Most devices use:

- Port: `34567`
- Username: `admin`
- Password: the password used by iCSee, or blank if the device has no local password

## Automation Example

```yaml
automation:
  - alias: Feed fish every morning
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: icsee_feeder.feed
        target:
          entity_id: button.fish_feeder_feed
        data:
          servings: 1
```

## Notes

The underlying feeder commands are `OPFeedManual`, `OPFeedBook`, and `OPFeedHistory`. If setup works but feeding does not, enable debug logging and check whether your feeder firmware returns a non-`100` DVRIP response code.

```yaml
logger:
  logs:
    custom_components.icsee_feeder: debug
```

