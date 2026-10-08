import json
import unittest
import match_review as r

ME, OPP = 2, 1
NAMES = {10: 'Forest', 11: 'Swamp', 20: 'Shoot the Sheriff', 21: 'Vraska, the Cutting Glare', 22: 'Duress',
         30: 'Ajani\'s Pridemate', 31: 'Plains', 900: 'Wrong Ability Name'}
MANA = {10: '', 11: '', 20: 'o1oB', 21: 'oBoBoG', 22: 'oB', 30: 'o1oW', 31: ''}


class FakeCards:
    def name(self, grp): return NAMES.get(grp, f'#{grp}')
    def mana_value(self, grp): return r.mana_value(MANA.get(grp, ''))


def gre(*messages):
    return json.dumps({'greToClientEvent': {'greToClientMessages': list(messages)}})


def state(turn=None, active=None, phase=None, objects=(), zones=(), annotations=(), players=(), game=1, stage=None, results=None):
    g = {'gameObjects': list(objects), 'zones': list(zones), 'annotations': list(annotations), 'players': list(players),
         'gameInfo': {'gameNumber': game}}
    if stage: g['gameInfo']['stage'] = stage
    if results: g['gameInfo']['results'] = results
    if turn: g['turnInfo'] = {'turnNumber': turn, 'activePlayer': active, 'phase': phase}
    return {'type': 'GREMessageType_GameStateMessage', 'gameStateMessage': g}


def obj(iid, grp, owner, types=('CardType_Land',), tapped=False, **kw):
    return dict(instanceId=iid, grpId=grp, ownerSeatId=owner, controllerSeatId=owner, cardTypes=list(types),
                isTapped=tapped, type=kw.pop('type', 'GameObjectType_Card'), **kw)


def zone(zid, ztype, owner, ids):
    return {'zoneId': zid, 'type': 'ZoneType_' + ztype, 'ownerSeatId': owner, 'objectInstanceIds': list(ids)}


def transfer(iid, category, src, dst, affector=None):
    a = {'type': ['AnnotationType_ZoneTransfer'], 'affectedIds': [iid],
         'details': [{'key': 'category', 'valueString': [category]}, {'key': 'zone_src', 'valueInt32': [src]},
                     {'key': 'zone_dest', 'valueInt32': [dst]}]}
    if affector: a['affectorId'] = affector
    return a


def mana_paid(source, spell):
    return {'type': ['AnnotationType_ManaPaid'], 'affectorId': source, 'affectedIds': [spell], 'details': []}


def damage(source, target, amount):
    return {'type': ['AnnotationType_DamageDealt'], 'affectorId': source, 'affectedIds': [target],
            'details': [{'key': 'damage', 'valueInt32': [amount]}]}


# zone ids: 1 my hand, 2 battlefield, 3 stack, 4 my graveyard, 5 opp graveyard, 6 my library, 7 opp hand
def match_log(match_id='m1', completed=True, undone_cast=False, resolve_without_zone=False, ownerless_sacrifice=False):
    lines = [f'[UnityCrossThreadLogger]Connecting to matchId {match_id}',
             json.dumps({'matchGameRoomStateChangedEvent': {'gameRoomInfo': {'stateType': 'MatchGameRoomStateType_Playing',
                         'gameRoomConfig': {'matchId': match_id, 'reservedPlayers': [
                             {'playerName': 'Opp', 'systemSeatId': OPP}, {'playerName': 'WintersRain', 'systemSeatId': ME}]}}}}),
             gre({'type': 'GREMessageType_ConnectResp', 'connectResp': {'deckMessage': {'deckCards': [20, 20, 21, 10, 11], 'sideboardCards': [22]}}}),
             gre({'type': 'GREMessageType_MulliganReq'}), gre({'type': 'GREMessageType_MulliganReq'})]
    hand = [obj(101, 20, ME, ('CardType_Instant',)), obj(102, 21, ME, ('CardType_Creature',)), obj(103, 10, ME)]
    lands = [obj(201, 11, ME), obj(202, 10, ME)]
    lines.append(gre(state(1, ME, 'Phase_Beginning', objects=hand + lands, players=[{'systemSeatNumber': ME, 'lifeTotal': 20}, {'systemSeatNumber': OPP, 'lifeTotal': 20}],
                           zones=[zone(1, 'Hand', ME, [101, 102, 103]), zone(2, 'Battlefield', 0, [201, 202]), zone(3, 'Stack', 0, []),
                                  zone(4, 'Graveyard', ME, []), zone(5, 'Graveyard', OPP, []), zone(6, 'Library', ME, [104]), zone(7, 'Hand', OPP, [])])))
    # my turn 1: draw 104 in the draw step (before main), main: nothing cast (Sheriff castable, held)
    lines.append(gre(state(1, ME, 'Phase_Beginning', objects=[obj(104, 31, ME)], zones=[zone(1, 'Hand', ME, [101, 102, 103, 104]), zone(6, 'Library', ME, [])],
                           annotations=[transfer(104, 'Draw', 6, 1)])))
    lines.append(gre(state(1, ME, 'Phase_Main1')))
    # opponent turn 2: Pridemate, then attacks me for 2
    lines.append(gre(state(2, OPP, 'Phase_Main1', objects=[obj(301, 30, OPP, ('CardType_Creature',), power={'value': 2}, toughness={'value': 2})],
                           zones=[zone(2, 'Battlefield', 0, [201, 202, 301])], annotations=[transfer(301, 'CastSpell', 7, 3)])))
    lines.append(gre(state(2, OPP, 'Phase_Combat', annotations=[damage(301, ME, 2)], players=[{'systemSeatNumber': ME, 'lifeTotal': 18}])))
    # my turn 3: lands were tapped on turn 2; the untap update omits isTapped (Arena drops false fields)
    lines.append(gre(state(2, OPP, 'Phase_Ending', objects=[obj(201, 11, ME, tapped=True), obj(202, 10, ME, tapped=True)])))
    untapped = [{k: v for k, v in obj(i, g, ME).items() if k != 'isTapped'} for i, g in ((201, 11), (202, 10))]
    lines.append(gre(state(3, ME, 'Phase_Main1', objects=untapped)))
    # Sheriff (2 mana paid by my lands) kills Pridemate; ability object named via its parent
    lines.append(gre(state(3, ME, 'Phase_Main1', objects=[obj(101, 20, ME, ('CardType_Instant',))], zones=[zone(1, 'Hand', ME, [102, 103, 104]), zone(3, 'Stack', 0, [101])],
                           annotations=[transfer(101, 'CastSpell', 1, 3), mana_paid(201, 101), mana_paid(202, 101)])))
    resolve = transfer(101, 'Resolve', 3, 4)
    if resolve_without_zone:  # real logs do not always carry zone ids on Resolve
        resolve['details'] = [x for x in resolve['details'] if x['key'] == 'category']
    sac = []
    if ownerless_sacrifice:  # an object update without owner fields must not be attributed to the opponent
        lines.append(gre(state(3, ME, 'Phase_Main1', objects=[{'instanceId': 501, 'grpId': 31, 'cardTypes': ['CardType_Artifact']}])))
        sac = [transfer(501, 'Sacrifice', 2, 4, affector=101)]
    # Arena re-ids a card as it changes zones; the new id arrives with no owner info.
    id_change = {'type': ['AnnotationType_ObjectIdChanged'], 'affectedIds': [301],
                 'details': [{'key': 'orig_id', 'valueInt32': [301]}, {'key': 'new_id', 'valueInt32': [302]}]}
    lines.append(gre(state(3, ME, 'Phase_Main1', zones=[zone(3, 'Stack', 0, []), zone(4, 'Graveyard', ME, [101]), zone(5, 'Graveyard', OPP, [302]), zone(2, 'Battlefield', 0, [201, 202])],
                           annotations=sac + [id_change, transfer(302, 'Destroy', 2, 5, affector=101), resolve])))
    lines.append(gre(state(3, ME, 'Phase_Main1', objects=[obj(401, 900, ME, ('CardType_Creature',), type='GameObjectType_Ability', parentId=102)],
                           annotations=[{'type': ['AnnotationType_PlayerSubmittedTargets'], 'affectorId': 401, 'affectedIds': [201], 'details': []}])))
    if undone_cast:  # Vraska cast then reverted: back in hand, never leaves the stack
        lines.append(gre(state(3, ME, 'Phase_Main1', annotations=[transfer(102, 'CastSpell', 1, 3)])))
    lines.append(gre(state(3, ME, 'Phase_Main1', zones=[zone(1, 'Hand', ME, [102, 103, 104])], stage='GameStage_GameOver',
                           results=[{'scope': 'MatchScope_Game', 'winningTeamId': ME, 'reason': 'ResultReason_Concede'}])))
    if completed:
        lines.append(json.dumps({'matchGameRoomStateChangedEvent': {'gameRoomInfo': {'stateType': 'MatchGameRoomStateType_MatchCompleted'}}}))
    return '\n'.join(lines) + '\n'


class MatchReviewTests(unittest.TestCase):
    def setUp(self):
        self.cards = FakeCards()

    def test_mana_value_from_arena_mana_text(self):
        self.assertEqual([r.mana_value(t) for t in ('o1oGoG', 'oXoRoR', 'o2o(B/G)', '', 'oBoBoG')], [3, 2, 3, 0, 3])

    def test_display_name_prefers_the_universes_beyond_title_over_omenpaths(self):
        import sqlite3
        db = sqlite3.connect(':memory:')
        db.executescript('''create table Cards (GrpId, TitleId, InterchangeableTitleId, ExpansionCode, OldSchoolManaText, IsToken);
            create table Localizations_enUS (LocId, Loc, Formatted);
            insert into Localizations_enUS values (1, 'Superior Spider-Man', 0), (2, 'Kavaero, Mind-Bitten', 0), (3, 'Forest', 0);
            insert into Cards values (97973, 1, 2, 'SPM', 'o2oUoB', 0), (104806, 2, 1, 'OM1', 'o2oUoB', 0), (5, 3, 0, 'FDN', '', 0);''')
        cards = r.CardDB(db)
        self.assertEqual([cards.name(g) for g in (97973, 104806, 5)], ['Superior Spider-Man', 'Superior Spider-Man', 'Forest'])
        self.assertEqual(cards.display('Kavaero, Mind-Bitten'), 'Superior Spider-Man')
        self.assertEqual(cards.display('Forest'), 'Forest')

    def test_split_returns_only_completed_matches_in_order(self):
        text = match_log('a') + match_log('b') + match_log('c', completed=False)
        self.assertEqual([m['match_id'] for m in r.split_matches(text)], ['a', 'b'])

    def test_seat_comes_from_reserved_players_not_a_default(self):
        self.assertEqual(r.seats(match_log()), {'Opp': OPP, 'WintersRain': ME})

    def test_review_turns_stats_and_ledger(self):
        review = r.review(match_log(), self.cards, 'WintersRain')
        g = review['games'][0]
        self.assertEqual((review['me'], review['opponent'], g['on_play'], g['mulligans'], g['result']), (ME, 'Opp', True, 1, 'win'))
        # the draw step belongs to turn 1, not to the previous turn
        self.assertIn(('Draw', 'Plains'), [(e['category'], e['card']) for e in g['turns'][1]['events'] if e['kind'] == 'zone'])
        self.assertEqual(g['turns'][1]['state']['my_hand'], ['Forest', 'Plains', 'Shoot the Sheriff', 'Vraska, the Cutting Glare'])
        s = g['stats']
        self.assertEqual(s['mana'][1], {'available': 2, 'spent': 0})
        self.assertEqual(s['mana'][3], {'available': 2, 'spent': 2})
        self.assertEqual(s['held_castable']['Shoot the Sheriff'], 1)   # castable on turn 1, held
        self.assertEqual(s['damage_taken_by_source'], {"Ajani's Pridemate": 2})
        self.assertEqual(s['first_interaction_turn'], 3)
        self.assertEqual(s['never_cast'], ['Vraska, the Cutting Glare'])
        targets = [e for e in g['turns'][3]['events'] if e['kind'] == 'target']
        self.assertEqual(targets[0]['source'], 'ability of Vraska, the Cutting Glare')
        self.assertEqual(review['deck']['main'], {'Shoot the Sheriff': 2, 'Vraska, the Cutting Glare': 1, 'Forest': 1, 'Swamp': 1})
        entry = r.ledger_entry(review)
        self.assertEqual((entry['match_id'], entry['opponent'], entry['games'][0]['result']), ('m1', 'Opp', 'win'))
        self.assertIn("Ajani's Pridemate", entry['opponent_cards'])
        self.assertEqual(len(entry['deck_sha256']), 64)

    def test_resolve_without_zone_ids_still_counts_as_cast(self):
        g = r.review(match_log(resolve_without_zone=True), self.cards, 'WintersRain')['games'][0]
        sheriff = [e for e in g['turns'][3]['events'] if e['kind'] == 'zone' and e['category'] == 'CastSpell']
        self.assertFalse(sheriff[0]['undone'])
        self.assertNotIn('Shoot the Sheriff', g['stats']['never_cast'])

    def test_ownerless_object_is_not_labeled_opponent(self):
        g = r.review(match_log(ownerless_sacrifice=True), self.cards, 'WintersRain')['games'][0]
        sac = [e for e in g['turns'][3]['events'] if e['kind'] == 'zone' and e['category'] == 'Sacrifice']
        self.assertNotEqual(sac[0]['seat'], 'opp')
        self.assertEqual(g['stats']['first_interaction_turn'], 3)   # still the Destroy, not the sacrifice

    def test_undone_cast_is_not_counted_as_a_cast(self):
        g = r.review(match_log(undone_cast=True), self.cards, 'WintersRain')['games'][0]
        casts = [e for e in g['turns'][3]['events'] if e['kind'] == 'zone' and e['category'] == 'CastSpell' and e['card'] == 'Vraska, the Cutting Glare']
        self.assertTrue(casts and casts[0]['undone'])
        self.assertEqual(g['stats']['never_cast'], ['Vraska, the Cutting Glare'])


if __name__ == '__main__':
    unittest.main()
