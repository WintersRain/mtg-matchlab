import unittest
from tools import gauntlet as g


class GauntletTests(unittest.TestCase):
    def test_plan_chunks_each_matchup_with_reproducible_seeds(self):
        jobs = g.plan(['jund', 'izzet'], games=60, seed=1000, chunk=24)
        self.assertEqual([(j['opponent'], j['seed'], j['games']) for j in jobs],
                         [('jund', 1000, 24), ('jund', 1024, 24), ('jund', 1048, 12),
                          ('izzet', 1000, 24), ('izzet', 1024, 24), ('izzet', 1048, 12)])

    def test_plan_requires_even_sizes_so_alternating_seats_stay_balanced(self):
        # Each chunk restarts seat alternation, so odd sizes would favor one seat.
        for games, chunk in ((61, 24), (60, 25)):
            with self.subTest(games=games, chunk=chunk), self.assertRaises(ValueError):
                g.plan(['jund'], games=games, seed=0, chunk=chunk)

    def test_tally_counts_only_completed_games_as_results(self):
        games = [{'status': 'completed', 'winner': 'seat-a'}, {'status': 'completed', 'winner': 'seat-b'},
                 {'status': 'draw', 'winner': None}, {'status': 'timeout', 'winner': None},
                 {'status': 'error', 'winner': None}, {'status': 'completed', 'winner': 'seat-a'}]
        self.assertEqual(g.tally(games), {'wins': 2, 'losses': 1, 'draws': 1, 'failed': 2, 'games': 4})

    def test_wilson_interval(self):
        lo, hi = g.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertEqual(g.wilson(0, 0), (0.0, 1.0))

    def test_weighted_rate_renormalizes_over_tested_opponents(self):
        per = {'a': {'wins': 30, 'games': 60}, 'b': {'wins': 15, 'games': 60}}
        rate, se = g.weighted(per, {'a': 0.09, 'b': 0.03, 'untested': 0.5})
        self.assertAlmostEqual(rate, (0.75 * 0.5 + 0.25 * 0.25))
        expected = ((0.75 ** 2) * 0.25 / 60 + (0.25 ** 2) * 0.25 * 0.75 / 60) ** 0.5
        self.assertAlmostEqual(se, expected)


if __name__ == '__main__':
    unittest.main()
