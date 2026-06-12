# Data Model MVP

## documents

One row per original file received from Telegram.

Key fields:

- id
- telegram_user_id
- telegram_message_id
- original_filename
- stored_path
- sha256
- mime_type
- document_type
- document_date
- user_comment
- processing_status

## timeline_items

One row per extracted or user-entered medical event.

Key fields:

- id
- document_id
- event_date
- event_type
- title
- body
- source_quote
- confidence
- verified_by_user
