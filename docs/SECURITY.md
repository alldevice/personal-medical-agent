# Security notes

This project is a personal medical archive assistant. Treat every runtime entry point as sensitive because the assistant may access private medical context, document metadata, timeline entries, and conversational memory.

## Telegram access control

The dedicated medical Telegram bot is a sensitive entry point. The bot username and bot link are not secrets: anyone who discovers them may try to send messages to the bot.

Every deployment **must** restrict inbound Telegram access to the owner or explicitly authorized users.

The `medical_consultant` Hermes profile must define an explicit allowlist in the profile environment file:

```text
/home/hermes/.hermes/profiles/medical_consultant/.env
```

Required profile variables:

```text
TELEGRAM_BOT_TOKEN=<medical bot token>
TELEGRAM_ALLOWED_USERS=XXX
HERMES_MEDICAL_PROFILE=medical_consultant
```

`XXX` must be replaced with the Telegram numeric user id of the person who owns or administers the deployment. Do not document or commit a real production Telegram user id in this repository unless it is intentionally public test data.

Security rules:

- Do not run `hermes-medical-consultant-gateway.service` without `TELEGRAM_ALLOWED_USERS`.
- Do not rely on the bot token, bot username, or obscurity as access control.
- Do not reuse a shared public Telegram bot token for the medical profile.
- Do not commit Telegram tokens, real user ids, medical data, local `.env` files, or runtime caches.
- Treat a missing or ineffective allowlist as a security incident for the medical assistant contour.

## Runtime verification

Before treating a deployment as safe, verify both configuration and behavior.

Configuration check:

```bash
sudo grep -nE '^(TELEGRAM_BOT_TOKEN|TELEGRAM_ALLOWED_USERS)=' \
  /home/hermes/.hermes/profiles/medical_consultant/.env \
  | sed -E 's/(TELEGRAM_BOT_TOKEN=).*/\1<REDACTED>/'
```

Expected shape:

```text
TELEGRAM_BOT_TOKEN=<REDACTED>
TELEGRAM_ALLOWED_USERS=XXX
```

Behavior check:

1. Send a normal smoke-test message from the allowed Telegram account.
2. Send a message to the same bot from a second Telegram account that is not in `TELEGRAM_ALLOWED_USERS`.
3. Expected result: the unauthorized account must receive no useful response and must not reach the medical assistant, local vault, timeline, search, or memory context.

If an unauthorized Telegram account can receive a useful medical assistant response, stop the gateway immediately:

```bash
sudo systemctl stop hermes-medical-consultant-gateway.service
```

Then inspect the profile `.env`, the gateway configuration, and the Hermes Telegram access-control behavior before restarting the service.

## Public-release checklist

Before making the repository public or linking it from social media:

- Confirm that no real medical files or extracted medical text are committed.
- Confirm that no Telegram tokens or provider credentials are committed.
- Confirm that no real production Telegram user id is committed.
- Confirm that `TELEGRAM_ALLOWED_USERS=XXX` is documented as mandatory for private deployments.
- Confirm with a second Telegram account that unauthorized access is denied in the live deployment.
