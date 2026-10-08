import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import matchlab as m
import dashboard as d

class DashboardTests(unittest.TestCase):
    def test_about_name_and_two_independent_seats(self):
        a = 'About\nName A\n\nDeck\n60 Plains\n'
        b = 'About\nName B\n\nDeck\n60 Island\n'
        with patch.object(m, 'card_index', return_value={'Plains': {}, 'Island': {}}):
            pair = d.prepare_pair({'a': {'text': a}, 'b': {'text': b}})
        self.assertEqual(pair['seat-a'][0]['main'], {'Plains': 60})
        self.assertEqual(pair['seat-b'][1]['name'], 'B')
        self.assertNotEqual(pair['seat-a'][1]['source_sha256'], pair['seat-b'][1]['source_sha256'])

    def test_unsupported_both_seats_reported(self):
        with patch.object(m, 'card_index', return_value={}):
            with self.assertRaisesRegex(ValueError, 'seat-a.*Plains.*seat-b.*Island'):
                d.prepare_pair({'a': {'text': 'Deck\n60 Plains'}, 'b': {'text': 'Deck\n60 Island'}})

    def test_replay_preserves_real_order_without_board_inference(self):
        log = 'Startup\nTurn: Turn 1 (Ai(1)-seat-a)\nSpell: Plains\nGame Result: Game 1 ended in a Draw! Took 1 ms.\n'
        replay = d.replay(log)
        self.assertEqual([r['text'] for r in replay], log.splitlines())
        self.assertFalse(any('board' in r for r in replay))

    def test_invalid_headers_and_batch_bounds(self):
        for text in ['About\nDeck\n60 Island', 'Name A\nDeck\n60 Island', 'About\nName A\nCommander\n60 Island']:
            with self.assertRaises(ValueError): d.import_text(text)
        for body in [{'games': 0}, {'games': 51}, {'games': True}, {'seed': -1}, {'reuse': 'yes'}]:
            with self.assertRaises(ValueError): d.batch_settings(body)

    def test_reused_batch_records_each_game_and_increments_next_matchup_seed(self):
        calls=[]
        def run(body, on_game=None, stop_path=None):
            calls.append((body,stop_path))
            for n in range(body['games']):
                on_game({'status':'completed','seed':body['seed']+n,'winner':'seat-a'})
            return {'status':'completed','session_directory':'runtime/reuse/test'}
        with tempfile.TemporaryDirectory() as folder, patch.object(d,'DATA',Path(folder)), patch.object(d,'series',side_effect=run):
            (Path(folder)/'batches').mkdir()
            d.batch_worker('a'*32,{'a':{'text':'candidate'},'opponents':[{'selector':'first'},{'selector':'second'}],'games':2,'seed':77,'reuse':True,'alternate':True})
            import json
            state=json.loads((Path(folder)/'batches'/('a'*32+'.json')).read_text())
        self.assertEqual([c[0]['seed'] for c in calls],[77,79])
        self.assertEqual([r['seed'] for r in state['games']],[77,78,79,80])
        self.assertEqual(state['status'],'finished')
        self.assertTrue(all(c[0]['alternate'] for c in calls))
        self.assertEqual([c[0]['b']['selector'] for c in calls],['first','second'])

    def test_same_deck_still_has_distinct_engine_seats(self):
        with patch.object(m, 'card_index', return_value={'Island': {}}):
            pair = d.prepare_pair({'a': {'text': 'Deck\n60 Island'}, 'b': {'text': 'Deck\n60 Island'}})
        self.assertEqual(list(pair), ['seat-a', 'seat-b'])

    def test_snapshot_retains_exact_arena_text_and_header(self):
        text = 'About\nName Named deck\n\nDeck\n60 Island (ABC) 12\n'
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'card_index', return_value={'Island': {}}), patch.object(d.subprocess, 'check_output', return_value=m.PIN):
            pair = d.prepare_pair({'a': {'text': text}, 'b': {'text': text}})
            out = Path(folder)/'audit'
            report = d.audit_pair(pair, out)
            self.assertEqual((out/'seat-a.arena.txt').read_text(), text)
            self.assertEqual(report['decks']['seat-a']['source_sha256'], m.sha(text.encode()))
            self.assertNotIn('arena_text', report['decks']['seat-a'])

    def test_real_snapshot_parsing_and_legacy_duplicate_log(self):
        import json
        frame={'version':1,'event':'GameEventTurnBegan','turn':3,'players':[{'id':0,'life':17,'zones':{'Battlefield':[{'name':'Forest','tapped':True}]}}]}
        log='MATCHLAB_SNAPSHOT '+json.dumps(frame)+'\nTurn: Turn 3\nLife: 17\n'
        rows=d.replay(log)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['snapshot']['players'][0]['life'],17)
        self.assertEqual(rows[0]['snapshot']['players'][0]['zones']['Battlefield'][0]['name'],'Forest')

    def test_snapshot_errors_are_never_hidden(self):
        import json
        frame={'version':1,'event':'Initial','players':[]}
        rows=d.replay('MATCHLAB_SNAPSHOT '+json.dumps(frame)+'\nMATCHLAB_SNAPSHOT_ERROR Test failure\n')
        self.assertEqual(len(rows),2)
        self.assertIn('ERROR',rows[1]['text'])
        self.assertFalse(any('snapshot' in r for r in d.replay('MATCHLAB_SNAPSHOT {"version":1}\n')))

    def test_explicit_engine_deltas_materialize_without_state_guessing(self):
        import json
        first={'version':1,'game':1,'event':'Initial','players':[{'id':0,'life':20,'zones':{'Battlefield':[],'Hand':[{'name':'Forest'}]}}]}
        second={'version':1,'game':1,'event':'GameEventLandPlayed','delta':True,'players':[{'id':0,'life':19,'zones':{'Battlefield':[{'name':'Forest','tapped':False}],'Hand':[]}}]}
        third={'version':1,'game':1,'event':'GameEventTurnBegan','delta':True,'turn':2,'players':[{'id':0,'life':19,'zones':{}}]}
        rows=d.replay(''.join('MATCHLAB_SNAPSHOT '+json.dumps(x)+'\n' for x in [first,second,third]))
        self.assertEqual(rows[0]['snapshot']['players'][0]['life'],20)
        self.assertEqual(rows[1]['snapshot']['players'][0]['zones']['Hand'],[])
        self.assertEqual(rows[2]['snapshot']['players'][0]['zones']['Battlefield'],[{'name':'Forest','tapped':False}])
        self.assertEqual(rows[2]['snapshot']['turn'],2)
        self.assertNotIn('snapshot',d.replay('MATCHLAB_SNAPSHOT '+json.dumps(second)+'\n')[0])

if __name__ == '__main__': unittest.main()
