import unittest
import reuse_runner as r

class ReuseRunnerInputTests(unittest.TestCase):
    def test_incremented_seed_boundary(self):
        self.assertEqual(r.settings({'games':3,'seed':2**63-3}),(3,2**63-3))
        for body in ({'games':3,'seed':2**63-2},{'games':0},{'games':51},
                     {'games':True},{'seed':True},{'alternate':1},{'snapshots':'false'}):
            with self.subTest(body=body),self.assertRaises(ValueError):r.settings(body)

    def test_logical_seats_independent_of_alternation_start(self):
        self.assertEqual([r.expected_seats({'alternate':True},i) for i in range(3)],
                         [['seat-a','seat-b'],['seat-b','seat-a'],['seat-a','seat-b']])
        self.assertEqual(r.expected_seats({'alternate':True,'swap':True},0),['seat-b','seat-a'])
        self.assertEqual(r.expected_seats({'alternate':True,'swap':True},1),['seat-a','seat-b'])

    def test_marker_requires_json_object(self):
        self.assertIsNone(r.marker('Turn: Turn 1','MATCHLAB_GAME_BEGIN '))
        self.assertEqual(r.marker('MATCHLAB_GAME_BEGIN {"game":1,"seed":42}',
                                  'MATCHLAB_GAME_BEGIN '),{'game':1,'seed':42})
        for value in ('[]','null','"seed"'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                r.marker('MATCHLAB_GAME_BEGIN '+value,'MATCHLAB_GAME_BEGIN ')

if __name__=='__main__':unittest.main()

