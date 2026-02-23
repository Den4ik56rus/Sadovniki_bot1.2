-- schema_68: Allow 'system' direction in messages table
-- Needed for token deduction system messages in client chat feed

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_direction_check;

ALTER TABLE messages ADD CONSTRAINT messages_direction_check
    CHECK (direction IN ('user', 'bot', 'assistant', 'system'));
