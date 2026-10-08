import unittest
import analysis_tools as a
from opening_audit import Pilot

class LandTimingTests(unittest.TestCase):
    def test_town_late_first_land_enters_tapped(self):
        c={'deck_size':12,'opening_hand':7,'on_play':True,'lands':[{'name':'Starting Town','count':1,'model':'starting_town','colors':list('WUBRG'),'types':[]}], 'targets':[{'name':'W','turn':4,'colored':{'W':1},'generic':0,'artifact':False}]}
        # Town is drawn turn four after three missed land drops.
        self.assertIsNone(a.minimum_life(c,[-1]*9+[0]+[-1]*2,c['targets'][0]))
    def test_tapped_land_not_available_on_entry(self):
        p=Pilot({'Tri':{'land':True,'model':'tapped','colors':'WBR','types':[]},'w':{'land':False,'body':True,'cost':'{W}'}})
        r=p.turn(('Tri','w'),(),(),1)
        self.assertEqual(r['casts'],())
        self.assertTrue(r['tapped'])
        self.assertEqual(p.turn(('w',),('Tri',),(),2)['casts'],('w',))
    def test_two_tapped_lands_delay_double_pip_until_three(self):
        p=Pilot({'Tri':{'land':True,'model':'tapped','colors':'WBR','types':[]},'ww':{'land':False,'body':True,'cost':'{W}{W}'}})
        r=p.play(('Tri','Tri','ww'),(),True,trace=True)
        self.assertFalse(r['early_body'])
        self.assertEqual(r['trace'][2]['casts'],('ww',))

    def test_run_reports_retained_sizes_and_taps(self):
        cards={'Tri':{'land':True,'model':'tapped','colors':'WBR','types':[]},'w':{'land':False,'body':True,'cost':'{W}'}}
        p=Pilot(cards)
        self.assertEqual(p.play(('Tri','w'),(),True)['tapped_entries'],1)
        self.assertEqual(p.play(('Tri','w'),(),True)['mana_spent'],1)
        import opening_audit
        c=opening_audit.run({'cards':cards,'candidates':{'a':['Tri']*25+['w']*35}},20,42)['summary']['a']['play']['counts']
        self.assertEqual(sum(c.get('accepted'+str(n),0) for n in [5,6,7]),20)
        self.assertIn('accepted6_early',c)

if __name__=='__main__':unittest.main()
