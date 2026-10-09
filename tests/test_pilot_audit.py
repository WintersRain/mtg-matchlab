import unittest
from tools import pilot_audit as pa
from tools import vet

SCRIPTS = {
    'Swamp': 'Name:Swamp\nManaCost:no cost\nTypes:Basic Land Swamp\nOracle:({T}: Add {B}.)',
    'Scorn': 'Name:Scorn\nManaCost:1 B\nTypes:Sorcery\nOracle:Target creature gets -3/-3 until end of turn.',
    'Hex': 'Name:Hex\nManaCost:B\nTypes:Instant\nOracle:Destroy target creature with mana value 2 or less.',
    'Ogre': 'Name:Ogre\nManaCost:4 B\nTypes:Creature Ogre\nPT:5/5\nOracle:',
    'Verge': 'Name:Verge\nManaCost:no cost\nTypes:Land\nOracle:{T}: Add {B}.\\n{T}: Add {R}. Activate only if you control a Swamp or a Mountain.',
    'Claw': 'Name:Claw\nManaCost:R\nTypes:Creature Lizard\nPT:2/1\nOracle:',
    'Goblin':'Name:Goblin\nManaCost:R\nTypes:Creature Goblin\nPT:1/1\nOracle:',
}
CARDS = {n: vet.parse_script(t) for n, t in SCRIPTS.items()}


def card(name, tapped=False, creature=False, land=False):
    return {'name': name, 'tapped': tapped, 'creature': creature, 'land': land}


def frame(turn, active, phase, mine_hand, mine_field, theirs_field, lands_played=1):
    players = [{'id': 0, 'lands_played_this_turn': lands_played if active == 0 else 0,
                'zones': {'Hand': mine_hand, 'Battlefield': mine_field}},
               {'id': 1, 'lands_played_this_turn': 0, 'zones': {'Hand': [], 'Battlefield': theirs_field}}]
    return {'turn': turn, 'active_player': active, 'phase': phase, 'players': players}


class IdleTurnTests(unittest.TestCase):
    def test_flags_sorcery_removal_held_with_mana_and_a_target(self):
        f = [frame(5, 0, 'MAIN1', [card('Scorn')], [card('Swamp', land=True)] * 3, [card('Goblin', creature=True)]),
             frame(5, 0, 'END_OF_TURN', [card('Scorn')], [card('Swamp', land=True)] * 3, [card('Goblin', creature=True)])]
        idle = pa.idle_turns(f, CARDS)
        self.assertEqual([(i['turn'], i['player'], i['castable']) for i in idle], [(5, 0, ['Scorn'])])

    def test_holding_an_instant_is_allowed(self):
        f = [frame(5, 0, 'END_OF_TURN', [card('Hex')], [card('Swamp', land=True)] * 3, [card('Goblin', creature=True)])]
        self.assertEqual(pa.idle_turns(f, CARDS), [])

    def test_removal_without_a_target_is_not_castable(self):
        f = [frame(5, 0, 'END_OF_TURN', [card('Scorn')], [card('Swamp', land=True)] * 3, [])]
        self.assertEqual(pa.idle_turns(f, CARDS), [])

    def test_not_enough_untapped_mana_is_not_idle(self):
        f = [frame(5, 0, 'END_OF_TURN', [card('Ogre')], [card('Swamp', land=True)] * 3 + [card('Swamp', tapped=True, land=True)] * 2, [])]
        self.assertEqual(pa.idle_turns(f, CARDS), [])

    def test_unplayed_land_in_hand_is_flagged(self):
        f = [frame(3, 0, 'END_OF_TURN', [card('Swamp', land=True)], [card('Swamp', land=True)] * 2, [], lands_played=0)]
        self.assertTrue(pa.idle_turns(f, CARDS)[0]['missed_land'])


class ConditionalLandTests(unittest.TestCase):
    def test_verge_makes_its_second_color_only_with_the_named_land_type(self):
        alone = [frame(2, 0, 'END_OF_TURN', [card('Claw')], [card('Verge', land=True)], [])]
        self.assertEqual(pa.idle_turns(alone, CARDS), [])
        with_swamp = [frame(3, 0, 'END_OF_TURN', [card('Claw')], [card('Verge', land=True), card('Swamp', tapped=True, land=True)], [])]
        self.assertEqual(pa.idle_turns(with_swamp, CARDS)[0]['castable'], ['Claw'])

    def test_turn_ended_frame_belongs_to_the_next_player_and_is_ignored(self):
        f = [frame(1, 0, 'END_OF_TURN', [], [card('Swamp', land=True)], []),
             dict(frame(1, 1, 'CLEANUP', [card('Swamp', land=True)], [], [], lands_played=0), event='GameEventTurnEnded')]
        self.assertEqual(pa.idle_turns(f, CARDS), [])


class HoldingTests(unittest.TestCase):
    def test_keeping_mana_up_for_an_instant_in_hand_is_not_idle(self):
        f = [frame(5, 0, 'END_OF_TURN', [card('Scorn'), card('Hex')], [card('Swamp', land=True)] * 2, [card('Goblin', creature=True)])]
        self.assertEqual(pa.idle_turns(f, CARDS), [])

    def test_restricted_mana_land_does_not_count_for_colors(self):
        cavern = vet.parse_script('Name:Cavern\nManaCost:no cost\nTypes:Land\nOracle:{T}: Add {C}.\\n{T}: Add one mana of any color. '
                                  'Spend this mana only to cast a creature spell of the chosen type.')
        self.assertEqual(cavern['produces'], set())


class VerdictTests(unittest.TestCase):
    def test_game_with_repeated_idle_turns_is_invalid(self):
        idle = [{'player': 0, 'turn': 3}, {'player': 0, 'turn': 5}]
        self.assertFalse(pa.game_valid(idle, max_idle=1))
        self.assertTrue(pa.game_valid(idle[:1], max_idle=1))


if __name__ == '__main__':
    unittest.main()
