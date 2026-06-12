# Deprecated profile name: medical_agent

This profile name is deprecated.

Use `profiles/medical_consultant/PROFILE.md` and the Hermes profile named `medical_consultant` instead.

Reason: the live MVP uses a dedicated Telegram bot and systemd gateway service:

```text
/etc/systemd/system/hermes-medical-consultant-gateway.service
/home/hermes/.hermes/profiles/medical_consultant
/srv/hermes-medical/data
```
