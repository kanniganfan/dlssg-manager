# DLSSG Manager v1.9.4

- "Restart GPU" no longer ends in a raw PnP error. If Windows has already flagged the display device as pending a reboot (`DN_NEED_RESTART`), the app detects it, says a reboot is required, and shows a "Reboot PC" button instead of running a restart that cannot succeed.
- The restart path now falls back from `pnputil /restart-device` to the Device Manager equivalent (`Disable-PnpDevice` + `Enable-PnpDevice`) when pnputil reports `ERROR_NOT_SUPPORTED`.
- While the device is pending a restart, the masked-name line reads "takes effect after a reboot" rather than "click Restart GPU to apply now".
- Rebooting is scheduled with `shutdown /r /t 60`, so it can still be cancelled with `shutdown /a`.
