import unittest
from ramp_opening_audit import RampPilot, fetch_basic, run


def cards():
    return {
        'Forest':dict(land=True,model='basic',colors='G',types=['Forest']),
        'Mountain':dict(land=True,model='basic',colors='R',types=['Mountain']),
        'Shock':dict(land=True,model='shock',colors='RG',types=['Forest','Mountain']),
        'Compound':dict(land=True,model='compound',colors='C',types=[]),
        'Verge':dict(land=True,model='verge',colors='R',conditional='G',requires=['Forest','Mountain'],types=[]),
        'Elf':dict(land=False,cost='{G}',effect='elf'),
        'Roots':dict(land=False,cost='{1}{G}',effect='roots'),
        'Price':dict(land=False,cost='{1}{R}',effect='draw',draw=1),
        'Threat':dict(land=False,cost='{2}{R}{R}',effect='body',threat=True),
    }


class RampRulesTests(unittest.TestCase):
    def setUp(self):self.p=RampPilot(cards())
    def test_compound_shock_loses_colors(self):
        self.assertEqual(self.p.sources((('Compound',1,False),('Shock',2,False)),(),2),('C','RG'))
    def test_compound_basic_enables(self):
        self.assertEqual(self.p.sources((('Compound',1,False),('Forest',2,False)),(),2),('CRG','G'))
    def test_fresh_compound(self):
        self.assertEqual(self.p.sources((('Compound',1,False),),(),1),('CRG',))
    def test_double_verge(self):
        self.assertEqual(self.p.sources((('Verge',1,False),('Verge',2,False)),(),2),('R','R'))
    def test_roots_only_basic_tapped(self):
        deck=['Shock','Compound','Forest','Mountain'];lib=[0,1,2,3]
        land=fetch_basic(cards(),deck,lib,'Forest',2)
        self.assertEqual(land,('Forest',2,True));self.assertEqual(lib,[0,1,3])
        self.assertNotIn('G', ''.join(self.p.sources((land,),(),2)))
        self.assertIn('G', ''.join(self.p.sources((land,),(),3)))
        self.assertIsNone(fetch_basic(cards(),deck,[0,1],'Forest',2))
    def test_elf_sickness(self):
        self.assertEqual(self.p.sources((),(1,),1),())
        self.assertEqual(self.p.sources((),(1,),2),('G',))
    def test_payment_two_pips_distinct(self):
        self.assertFalse(self.p.can_pay(('RG',),'Threat'))
        self.assertTrue(self.p.can_pay(('R','R','G','G'),'Threat'))
    def test_price_draw_and_cumulative_shocks(self):
        p=self.p;deck=['Shock','Price','Shock','Price','Forest','Threat','Threat']+['Mountain']*10
        r=p.play(deck,[0,1,2,3,4,5,6],list(range(7,17)),True,22)
        self.assertEqual(sum(x['casts'].count('Price') for x in r['trace']),2)
        self.assertEqual(len([d for x in r['trace'] for d in x['effect_draws']]),2)
        self.assertEqual(r['life'],sum(x['shock_life'] for x in r['trace']))
    def test_blind_land_choice(self):
        hand=('Compound','Forest','Elf','Threat');a=self.p.choose_land(hand,(),(),1)
        self.assertEqual(a,self.p.choose_land(hand,(),(),1))
    def test_legendary_duplicate_not_cast(self):
        c=cards();c['Threat']['legendary']=True;p=RampPilot(c)
        self.assertIsNone(p.best_spell(['Threat'],('R','R','G','G'),4,['Threat']))
    def test_two_shocks_paid_cumulatively(self):
        c=cards();c['Joke']=dict(land=False,cost='{R}',effect='interaction');p=RampPilot(c)
        deck=['Shock','Shock','Joke','Price','Threat','Threat','Threat']+['Threat']*10
        r=p.play(deck,list(range(7)),list(range(7,17)),True,1)
        self.assertEqual(r['life'],4)
        self.assertEqual(r['trace'][0]['shock_life'],2)
        self.assertEqual(r['trace'][1]['shock_life'],2)
    def test_roots_enables_compound_midturn(self):
        p=self.p;deck=['Compound','Roots','Shock','Elf','Threat','Threat','Threat']+['Mountain']*10
        r=p.play(deck,list(range(7)),list(range(7,17)),True,3)
        roots=[t for t in r['trace'] if 'Roots' in t['casts']]
        self.assertTrue(roots)
        self.assertEqual(roots[0]['fetched'],['Mountain'])
        self.assertTrue(roots[0]['lands'][-1][2])
    def test_forced_five_and_no_library_keep_input(self):
        m,b,q,_=self.p.mulligan([['Threat']*7]*3)
        self.assertEqual((m,len(b),q),(2,2,False))
    def test_unknown_effect_rejected(self):
        c=cards();c['Elf']['effect']='invented'
        with self.assertRaises(ValueError):RampPilot(c)
    def test_paired_self_comparison(self):
        deck=['Forest']*14+['Mountain']*10+['Elf']*4+['Roots']*4+['Price']*4+['Threat']*24
        r=run(dict(cards=cards(),candidates={'a':deck,'b':deck}),12,91)
        self.assertEqual(r['summary']['a'],r['summary']['b'])
        self.assertTrue(all(v['delta']==0 for s in r['paired_deltas']['b'].values() for v in s.values()))

if __name__=='__main__':unittest.main()
