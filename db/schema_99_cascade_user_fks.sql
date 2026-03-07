-- schema_99: Add ON DELETE CASCADE to all user FK constraints missing it
-- This allows DELETE FROM users WHERE id = X to cascade to all related tables

-- payments
ALTER TABLE payments DROP CONSTRAINT payments_user_id_fkey;
ALTER TABLE payments ADD CONSTRAINT payments_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- user_subscriptions
ALTER TABLE user_subscriptions DROP CONSTRAINT user_subscriptions_user_id_fkey;
ALTER TABLE user_subscriptions ADD CONSTRAINT user_subscriptions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- payment_errors
ALTER TABLE payment_errors DROP CONSTRAINT payment_errors_user_id_fkey;
ALTER TABLE payment_errors ADD CONSTRAINT payment_errors_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- referrals
ALTER TABLE referrals DROP CONSTRAINT referrals_referrer_id_fkey;
ALTER TABLE referrals ADD CONSTRAINT referrals_referrer_id_fkey
    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE referrals DROP CONSTRAINT referrals_referee_id_fkey;
ALTER TABLE referrals ADD CONSTRAINT referrals_referee_id_fkey
    FOREIGN KEY (referee_id) REFERENCES users(id) ON DELETE CASCADE;

-- guide_orders
ALTER TABLE guide_orders DROP CONSTRAINT guide_orders_user_id_fkey;
ALTER TABLE guide_orders ADD CONSTRAINT guide_orders_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- broadcast_recipients
ALTER TABLE broadcast_recipients DROP CONSTRAINT broadcast_recipients_user_id_fkey;
ALTER TABLE broadcast_recipients ADD CONSTRAINT broadcast_recipients_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- broadcast_button_clicks
ALTER TABLE broadcast_button_clicks DROP CONSTRAINT broadcast_button_clicks_user_id_fkey;
ALTER TABLE broadcast_button_clicks ADD CONSTRAINT broadcast_button_clicks_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- broadcast_poll_answers
ALTER TABLE broadcast_poll_answers DROP CONSTRAINT broadcast_poll_answers_user_id_fkey;
ALTER TABLE broadcast_poll_answers ADD CONSTRAINT broadcast_poll_answers_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
