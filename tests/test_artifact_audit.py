import copy
import json
from pathlib import Path
import unittest

import artifact_audit as a

ROOT = Path(__file__).resolve().parents[1]


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((ROOT / 'examples/artifact-oracle.json').read_text())
        cls.cards = a.catalog(cls.bundle)

    def board(self, permanents=(), mana=(), hand=()):
        return a.Board(self.cards, {'permanents': list(permanents), 'mana': list(mana), 'hand': list(hand)})

    def test_exact_printing_and_front_identity(self):
        r = a.inspect_deck('Deck\n4 Heartwood Crafter (FRA) 105\n24 Forest (HOB) 198\n', self.bundle)
        self.assertEqual(r['counts']['main'], 28)
        self.assertEqual(r['curve'], {'1': 4})
        self.assertEqual(r['format'], None)
        self.assertEqual(r['arena']['missing_printing_ids'], ['Heartwood Crafter'])
        with self.assertRaisesRegex(ValueError, 'identity'):
            a.inspect_deck('Deck\n1 Forest (FRA) 105', self.bundle)

    def test_counts_not_silently_repaired(self):
        r = a.inspect_deck('Deck\n61 Forest (HOB) 198', self.bundle, 'standard')
        self.assertEqual(r['counts']['main'], 61)
        self.assertTrue(r['format_check']['minimum_main_met'])

    def test_missing_oracle_and_duplicate_printing_rejected(self):
        with self.assertRaises(ValueError):
            a.inspect_deck('Deck\n1 Unknown (XXX) 1', self.bundle)
        b = copy.deepcopy(self.bundle); b['records'].append(b['records'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            a.catalog(b)

    def test_changed_rules_fail_closed(self):
        cards = copy.deepcopy(self.cards)
        cards['Tenured Tethermage']['oracle_text'] = 'Create two untapped Heartwoods.'
        with self.assertRaisesRegex(ValueError, 'rules fingerprint'):
            a.Board(cards, {'permanents': [{'id': 't', 'name': 'Tenured Tethermage'}]})

    def test_tether_tapped_and_land_loss(self):
        b = self.board([{'id':'t','name':'Tenured Tethermage'}, {'id':'f','name':'Forest'}])
        b.step({'op':'tether_etb','id':'t','land':'f'})
        self.assertNotIn('f', b.permanents)
        self.assertEqual(len(b.permanents),3)
        self.assertTrue(all(p['tapped'] for p in b.permanents.values() if p['name']=='Heartwood'))
        with self.assertRaises(ValueError): b.step({'op':'tap_mana','id':'token1','color':'G'})
        with self.assertRaises(ValueError): b.step({'op':'tether_pump','id':'t','artifacts':['token1','token2']})

    def test_tether_etb_not_repeatable(self):
        b=self.board([{'id':'t','name':'Tenured Tethermage'}, {'id':'f','name':'Forest'}])
        b.step({'op':'tether_etb','id':'t'})
        with self.assertRaises(ValueError):b.step({'op':'tether_etb','id':'t','land':'f'})

    def test_pump_can_tap_new_artifact_creatures_but_not_twice(self):
        b=self.board([{'id':'t','name':'Tenured Tethermage'}, {'id':'r','name':'Ravenous Robots','new':True}, {'id':'e','name':'Edge Rover','new':True}])
        b.step({'op':'tether_pump','id':'t','artifacts':['r','e']})
        self.assertEqual(b.permanents['t']['counters'],2)
        with self.assertRaises(ValueError):b.step({'op':'tether_pump','id':'t','artifacts':['r','e']})

    def test_heartwood_mana_then_sacrifice_pays_own_activation(self):
        b=self.board([{'id':'b','name':'Hungering Puppetbeast'},{'id':'h','name':'Heartwood','new':True}])
        b.step({'op':'tap_mana','id':'h','color':'G'})
        b.step({'op':'puppet_sac','id':'b','sacrifice':'h','mode':'haste'})
        self.assertNotIn('h',b.permanents);self.assertEqual(b.permanents['b']['counters'],1)
        self.assertEqual(b.mana,[])

    def test_animated_new_heartwood_summoning_sickness_and_old_one(self):
        for new in [True,False]:
            b=self.board([{'id':'h','name':'Heartwood','new':new}],['G','C'],['Puppet Crafting'])
            b.step({'op':'cast','name':'Puppet Crafting','target':'h','id':'a'})
            if new:
                with self.assertRaisesRegex(ValueError,'summoning'):b.step({'op':'tap_mana','id':'h','color':'R'})
            else:b.step({'op':'tap_mana','id':'h','color':'R'})
            self.assertEqual(b.permanents['h']['base_power'],5)

    def test_restricted_crafter_mana_not_hand_but_prepared_spell(self):
        b=self.board([{'id':'c','name':'Heartwood Crafter'}],['G'],['Puppet Crafting'])
        b.step({'op':'tap_mana','id':'c','color':'C'})
        with self.assertRaisesRegex(ValueError,'mana'):b.step({'op':'cast','name':'Puppet Crafting','id':'a','target':'c'})
        b.mana.append({'color':'C','restriction':'none'})
        b.step({'op':'prepare_cast','id':'c'})
        self.assertFalse(b.permanents['c']['prepared'])
        self.assertEqual(sum(p['name']=='Heartwood' for p in b.permanents.values()),1)
        with self.assertRaises(ValueError):b.step({'op':'prepare_cast','id':'c'})

    def test_prodigy_does_not_enter_prepared(self):
        b=self.board([{'id':'w','name':'Woodwork Prodigy','new':True}],['G','C','C'])
        with self.assertRaisesRegex(ValueError,'prepared'):b.step({'op':'prepare_cast','id':'w'})
        b.step({'op':'next_turn'})
        self.assertTrue(b.permanents['w']['prepared'])

    def test_robots_cast_not_token_etb_or_self(self):
        b=self.board([],['R','C','G'],['Ravenous Robots','Edge Rover'])
        b.step({'op':'cast','name':'Ravenous Robots','id':'r'})
        self.assertEqual(len(b.permanents),1)
        b.step({'op':'cast','name':'Edge Rover','id':'e'})
        self.assertEqual(sum(p['name']=='Robot' for p in b.permanents.values()),1)

    def test_lander_actual_library_tapped_and_both_players(self):
        b=self.board([{'id':'e','name':'Edge Rover'}],['C','C'])
        b.library_basics={'Forest':1}
        b.step({'op':'die','id':'e'})
        self.assertEqual(b.opponent_landers,1)
        b.step({'op':'lander_fetch','id':'token1','basic':'Forest'})
        self.assertEqual(b.library_basics['Forest'],0)
        self.assertTrue(b.permanents['token2']['tapped'])

    def test_unsupported_effect_atomic_failure(self):
        b=self.board([],['R','C'],['The Last Agni Kai']);before=b.snapshot()
        with self.assertRaisesRegex(ValueError,'Unsupported'):b.step({'op':'cast','name':'The Last Agni Kai','id':'x'})
        self.assertEqual(b.snapshot(),before)

    def test_unknown_fields_rejected(self):
        b=self.board()
        with self.assertRaises(ValueError):b.step({'op':'next_turn','draw_cards':5})

    def test_thornspire_conditional_green(self):
        b=self.board([{'id':'v','name':'Thornspire Verge'},{'id':'r','name':'Restless Ridgeline'}])
        with self.assertRaises(ValueError):b.step({'op':'tap_mana','id':'v','color':'G'})
        b.add('s','Stomping Ground',tapped=True)
        b.step({'op':'tap_mana','id':'v','color':'G'})

    def test_prepared_shared_spell_name_is_not_import_alias(self):
        with self.assertRaisesRegex(ValueError,'identity'):
            a.inspect_deck('Deck\n1 Soul Tether (FRA) 105',self.bundle)

    def test_two_robots_trigger_first_only(self):
        b=self.board([{'id':'r','name':'Ravenous Robots'}],['R','C'],['Ravenous Robots'])
        b.step({'op':'cast','name':'Ravenous Robots','id':'r2'})
        self.assertEqual(sum(p['name']=='Robot' for p in b.permanents.values()),1)

    def test_soul_tether_token_does_not_trigger_robots(self):
        b=self.board([{'id':'r','name':'Ravenous Robots'},{'id':'c','name':'Heartwood Crafter'}],['G','C','C'])
        b.step({'op':'prepare_cast','id':'c'})
        self.assertEqual(sum(p['name']=='Robot' for p in b.permanents.values()),0)
        self.assertEqual(sum(p['name']=='Heartwood' for p in b.permanents.values()),1)

    def test_crafter_cannot_cast_solemn_from_hand(self):
        b=self.board([{'id':'c','name':'Heartwood Crafter'}],['G','R','C'],['Solemn Simulacrum'])
        b.step({'op':'tap_mana','id':'c','color':'C'})
        with self.assertRaisesRegex(ValueError,'mana'):b.step({'op':'cast','name':'Solemn Simulacrum','id':'s'})

    def test_sacrifice_solemn_draw_and_crafting_attachment(self):
        b=self.board([{'id':'b','name':'Hungering Puppetbeast'},{'id':'s','name':'Solemn Simulacrum'}],['C','C','G'],['Puppet Crafting'])
        b.step({'op':'cast','name':'Puppet Crafting','id':'a','target':'s'})
        b.step({'op':'puppet_sac','id':'b','sacrifice':'s','mode':'hexproof'})
        self.assertEqual(b.draw_triggers,1)
        self.assertIn('Puppet Crafting',b.graveyard)
        self.assertNotIn('a',b.permanents)

    def test_lander_cannot_fetch_shock_or_absent_basic(self):
        for target in ['Stomping Ground','Forest']:
            b=self.board([{'id':'l','name':'Lander'}],['C','C']);before=b.snapshot()
            with self.assertRaises(ValueError):b.step({'op':'lander_fetch','id':'l','basic':target})
            self.assertEqual(b.snapshot(),before)

    def test_aerid_counts_new_token(self):
        b=self.board([{'id':'a','name':'Aerid Konstrari'}],['C']*6)
        b.step({'op':'aerid_pump','id':'a'})
        self.assertIn('Aerid gains +1/+0 until end of turn',b.events)

    def test_robots_draw_availability_exact_enumeration(self):
        from itertools import combinations
        deck='Deck\n2 Ravenous Robots (TMT) 106\n2 Edge Rover (EOE) 179\n6 Forest (HOB) 198'
        r=a.inspect_deck(deck,self.bundle)
        slots=['R']*2+['A']*2+['L']*6
        expected=sum(sum(slots[i]=='R' for i in ix)>=1 and sum(slots[i] in 'RA' for i in ix)>=2 for ix in combinations(range(10),7))
        row=r['artifact_package']['robots_and_followup_artifact_draw_availability'][0]
        self.assertEqual(row['numerator'],expected)

    def test_wrong_cast_options_fail_closed(self):
        b=self.board([],['G'],['Edge Rover']);before=b.snapshot()
        with self.assertRaises(ValueError):b.step({'op':'cast','name':'Edge Rover','id':'e','basic':'Forest'})
        self.assertEqual(b.snapshot(),before)

    def test_illegal_crafting_target_rolls_back(self):
        b=self.board([{'id':'t','name':'Tenured Tethermage'}],['G','C'],['Puppet Crafting']);before=b.snapshot()
        with self.assertRaisesRegex(ValueError,'target'):b.step({'op':'cast','name':'Puppet Crafting','id':'a','target':'t'})
        self.assertEqual(b.snapshot(),before)

    def test_nonrules_face_metadata_does_not_break_fingerprint(self):
        b=copy.deepcopy(self.bundle)
        row=next(x for x in b['records'] if x['card']['name'].startswith('Heartwood Crafter'))
        row['card']['card_faces'][0]['artist']='Metadata only'
        a.Board(a.catalog(b),{'permanents':[{'id':'c','name':'Heartwood Crafter'}]})

    def test_exact_raw_input_hash(self):
        import hashlib
        text='Deck\r\n60 Forest (HOB) 198\r\n'
        r=a.inspect_deck(text,self.bundle)
        self.assertEqual(r['deck_sha256'],hashlib.sha256(text.encode()).hexdigest())


if __name__=='__main__':unittest.main()
