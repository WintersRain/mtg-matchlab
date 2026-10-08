import unittest
import opening_audit as a

class OpeningAuditTests(unittest.TestCase):
    def setUp(self):
        self.cards = {
            'F': {'land': True, 'model':'basic','colors':'G','types':['Forest']},
            'P': {'land': True, 'model':'basic','colors':'W','types':['Plains']},
            'V': {'land': True, 'model':'verge','colors':'R','conditional':'G','requires':['Mountain','Forest'],'types':[]},
            'S': {'land': True, 'model':'shock','colors':'RW','types':['Mountain','Plains']},
            'Fast': {'land': True, 'model':'fast','colors':'RW','types':[]},
            'g': {'land':False,'cost':'{G}','body':True,'legendary':False},
            'gg': {'land':False,'cost':'{G}{G}','body':True,'legendary':False},
            'rw': {'land':False,'cost':'{R}{W}','body':True,'legendary':True},
            'r': {'land':False,'cost':'{R}','body':True,'legendary':False},
            'removal': {'land':False,'cost':'{W}','body':False,'legendary':False}}
        self.p = a.Pilot(self.cards)
    def test_verge_requires_type_not_color(self):
        self.assertEqual(self.p.colors(('V','Fast')), ('R','RW'))
        self.assertEqual(self.p.colors(('V','F')), ('RG','G'))
    def test_no_double_spending_or_fake_body(self):
        result=self.p.turn(('g','g','removal'),('F',),(),2)
        self.assertEqual(len(result['casts']),1)
    def test_multispell_legal(self):
        result=self.p.turn(('g','g'),('F','F'),(),2)
        self.assertEqual(len(result['casts']),2)
    def test_shock_life_and_tapped_option(self):
        self.assertEqual(self.p.turn(('S','r'),(),(),1)['life'],2)
        self.assertEqual(self.p.turn(('S','rw'),(),(),1)['life'],0)
    def test_fast_fourth_tapped(self):
        self.assertEqual(self.p.turn(('Fast','rw'),('F','F','F'),(),4)['casts'],())
    def test_no_future_or_absent_spell(self):
        r=self.p.play(('F','P','removal'),(),True)
        self.assertFalse(r['early_body'])
        self.assertEqual(r,self.p.play(('F','P','removal'),(),True))
    def test_london_bottom_and_forced_floor(self):
        hands=[['F']*7,['P']*7,['F']*7]
        accepted,bottom,m,qualifies,offered=self.p.mulligan(hands)
        self.assertEqual((len(accepted),len(bottom),m,qualifies),(5,2,2,False))
    def test_functional_keep(self):
        self.assertTrue(self.p.keep(('F','F','g','gg','removal','removal','removal')))
        self.assertFalse(self.p.keep(('P','P','g','gg','removal','removal','removal')))
    def test_legend_duplicate_not_development(self):
        r=self.p.turn(('rw',),('S','S'),('rw',),3)
        self.assertEqual(r['casts'],())
    def test_unsupported_cost_rejected(self):
        with self.assertRaises(ValueError): a.parse_cost('{X}{G}')
    def test_colored_distinct_sources(self):
        self.assertEqual(a.payments(('RW',),'RW',0),())
    def test_actual_cast_exposure_and_cumulative_life(self):
        r=self.p.play(('S','S','r','rw'),(),True)
        self.assertEqual(r['life'],4)
        self.assertEqual(r['cast_names'],('r','rw'))
        self.assertFalse(r['color_stall'])
    def test_real_color_stall(self):
        r=self.p.play(('P','P','gg'),(),True)
        self.assertTrue(r['color_stall'])
        self.assertEqual(r['cast_names'],())
    def test_catalog_experimental_entry(self):
        from analysis_tools import CATALOG
        self.assertEqual(CATALOG['experimental_tools'][0]['command'],'python3 opening_audit.py')
    def test_pairing_self(self):
        cfg={'cards':self.cards,'candidates':{'a':['F']*24+['g']*36,'b':['F']*24+['g']*36}}
        r=a.run(cfg,20,42)
        self.assertEqual(r['summary']['a'],r['summary']['b'])

if __name__ == '__main__': unittest.main()
