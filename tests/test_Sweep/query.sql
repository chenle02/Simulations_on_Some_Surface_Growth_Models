.headers on
.mode column
SELECT id, type, width, sticky, final_steps, random_seed, slope FROM test_sweep ORDER BY type ASC, width ASC, sticky ASC, final_steps ASC, random_seed ASC, slope ASC;
