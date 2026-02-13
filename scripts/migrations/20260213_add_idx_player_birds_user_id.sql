-- Add index to speed up per-user bird counting/filtering queries used by brooding.
-- Safe to run multiple times.
CREATE INDEX IF NOT EXISTS idx_player_birds_user_id
ON public.player_birds (user_id);
