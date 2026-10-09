import unittest
from tools import vet

SCRIPT = {
    'Swamp': 'Name:Swamp\nManaCost:no cost\nTypes:Basic Land Swamp\nOracle:({T}: Add {B}.)',
    'Forest': 'Name:Forest\nManaCost:no cost\nTypes:Basic Land Forest\nOracle:({T}: Add {G}.)',
    'Tomb': 'Name:Tomb\nManaCost:no cost\nTypes:Land Swamp Forest\nOracle:({T}: Add {B} or {G}.)\\nAs Tomb enters, you may pay 2 life. If you don\'t, it enters tapped.',
    'Cottage': 'Name:Cottage\nManaCost:no cost\nTypes:Land\nOracle:Cottage enters tapped.\\n{T}: Add {B} or {G}.',
    'Glade': 'Name:Glade\nManaCost:no cost\nTypes:Land\nOracle:Glade enters tapped unless you control two or more other lands.\\n{T}: Add {B} or {G}.',
    'Hex': 'Name:Hex\nManaCost:B\nTypes:Instant\nOracle:Destroy target creature with mana value 2 or less.',
    'Bear': 'Name:Bear\nManaCost:1 G\nTypes:Creature Bear\nPT:2/2\nOracle:',
    'Dork': 'Name:Dork\nManaCost:B\nTypes:Creature Human\nPT:1/1\nOracle:{3}{B}, Sacrifice this creature: Return target creature card from your graveyard to the battlefield.',
    'Acolyte': 'Name:Acolyte\nManaCost:2 B B\nTypes:Creature Human\nPT:4/4\nOracle:Lifelink\\nWhenever one or more creatures you control deal combat damage to a player, you draw a card and lose 1 life.',
    'Ronin': 'Name:Ronin\nManaCost:4 B G\nTypes:Enchantment Saga\nOracle:I — Destroy all creatures.\\nII — Mill four cards.',
    'Wurm': 'Name:Wurm\nManaCost:3 B B B\nTypes:Creature Wurm\nPT:6/5\nOracle:When this creature enters, creatures your opponents control get -2/-2 until end of turn.',
    'Virtue': 'Name:Virtue\nManaCost:5 B B\nTypes:Enchantment\nOracle:At the beginning of your upkeep, put target creature card from a graveyard onto the battlefield under your control.\n'
              'ALTERNATE\nName:Scorn\nManaCost:1 B\nTypes:Sorcery Adventure\nOracle:Target creature gets -3/-3 until end of turn. You gain 2 life.',
}


def cards():
    return {name: vet.parse_script(text) for name, text in SCRIPT.items()}


class ParseTests(unittest.TestCase):
    def test_parses_cost_pips_types_and_body(self):
        c = cards()['Acolyte']
        self.assertEqual((c['mv'], c['pips'], c['power'], c['toughness']), (4, {'B': 2}, 4, 4))
        self.assertIn('Creature', c['types'])

    def test_adventure_face_gives_the_cheap_cost(self):
        c = cards()['Virtue']
        self.assertEqual((c['mv'], c['min_cost']), (7, 2))
        self.assertIn('-3/-3', c['text'])

    def test_lands_report_colors_and_unconditional_tapped(self):
        c = cards()
        self.assertEqual(c['Tomb']['produces'], {'B', 'G'})
        self.assertEqual(c['Swamp']['produces'], {'B'})
        self.assertTrue(c['Cottage']['enters_tapped'])
        self.assertFalse(c['Glade']['enters_tapped'])
        self.assertFalse(c['Tomb']['enters_tapped'])


def deck(**counts):
    return {'main': counts, 'sideboard': {}}


def status(report, check):
    return next(r['status'] for r in report['checks'] if r['check'] == check)


class CheckTests(unittest.TestCase):
    def test_flags_sweeper_that_kills_own_creatures(self):
        r = vet.vet(deck(Swamp=24, Bear=20, Ronin=4, Hex=12), cards())
        self.assertEqual(status(r, 'self-harm'), 'FAIL')

    def test_sweeper_in_a_low_creature_deck_is_only_a_warning(self):
        r = vet.vet(deck(Swamp=24, Bear=8, Ronin=4, Hex=24), cards())
        self.assertEqual(status(r, 'self-harm'), 'WARN')

    def test_one_sided_minus_effect_is_not_self_harm(self):
        r = vet.vet(deck(Swamp=24, Bear=20, Wurm=4, Hex=12), cards())
        self.assertEqual(status(r, 'self-harm'), 'PASS')

    def test_deck_of_do_nothing_bodies_fails_card_advantage_and_impact(self):
        r = vet.vet(deck(Swamp=24, Dork=24, Hex=12), cards())
        self.assertEqual(status(r, 'card advantage'), 'FAIL')
        self.assertEqual(status(r, 'low-impact cards'), 'FAIL')
        self.assertEqual(r['verdict'], 'FAIL')

    def test_counts_cheap_interaction_including_adventure_faces(self):
        r = vet.vet(deck(Swamp=24, Acolyte=24, Hex=4, Virtue=4, Bear=4), cards())
        row = next(x for x in r['checks'] if x['check'] == 'cheap interaction')
        self.assertEqual(row['value'], 8)

    def test_too_few_sources_for_an_early_color_fails(self):
        r = vet.vet(deck(Swamp=20, Forest=4, Bear=12, Acolyte=12, Hex=12), cards())
        self.assertEqual(status(r, 'colored sources'), 'FAIL')

    def test_too_many_tapped_lands_fails(self):
        r = vet.vet(deck(Cottage=13, Swamp=11, Acolyte=24, Hex=12), cards())
        self.assertEqual(status(r, 'tapped lands'), 'FAIL')

    def test_land_count_out_of_range_fails(self):
        r = vet.vet(deck(Swamp=18, Acolyte=30, Hex=12), cards())
        self.assertEqual(status(r, 'land count'), 'FAIL')

    def test_reasonable_midrange_shell_passes(self):
        r = vet.vet(deck(Swamp=24, Hex=4, Virtue=4, Acolyte=20, Wurm=8), cards())
        self.assertEqual(r['verdict'], 'PASS', r['checks'])


class ForgeTests(unittest.TestCase):
    def test_smoke_fails_on_a_lopsided_matchup(self):
        per = {'aggro': {'wins': 4, 'losses': 16, 'games': 20}, 'control': {'wins': 12, 'losses': 8, 'games': 20}}
        row = vet.forge_check(per)
        self.assertEqual(row['status'], 'FAIL')
        self.assertIn('aggro', row['detail'])

    def test_smoke_passes_when_no_matchup_is_a_blowout(self):
        per = {'aggro': {'wins': 9, 'losses': 11, 'games': 20}, 'control': {'wins': 12, 'losses': 8, 'games': 20}}
        self.assertEqual(vet.forge_check(per)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
