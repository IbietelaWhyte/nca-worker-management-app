-- Alter the availability table to add a constraint that ensures worker_id is unique for each day_of_week, 
-- preventing duplicate availability entries for the same worker on the same day.
ALTER TABLE public.availability
ADD CONSTRAINT unique_worker_day UNIQUE (worker_id, day_of_week);