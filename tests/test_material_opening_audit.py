import unittest
from material_opening_audit import passage, entry_tapped
class FetchTests(unittest.TestCase):
 def test_three_stays_tapped_and_consumes_library(self):
  lib=['Forest','Spell']; self.assertEqual(passage(lib,'Forest',3),('Forest',True));self.assertEqual(lib,['Spell'])
 def test_four_untaps_not_three_other_after_sacrifice(self):
  lib=['Island'];self.assertEqual(passage(lib,'Island',4),('Island',False))
 def test_exhaustion_not_rainbow(self):
  lib=['Forest'];self.assertIsNone(passage(lib,'Swamp',4));self.assertEqual(lib,['Forest'])
 def test_restriction(self):
  with self.assertRaises(ValueError):passage(['Breeding Pool'],'Breeding Pool',4)
 def test_tapped_models(self):
  self.assertTrue(entry_tapped('tapped',0,False));self.assertFalse(entry_tapped('fast',2,False));self.assertTrue(entry_tapped('fast',3,False));self.assertTrue(entry_tapped('shock',0,False));self.assertFalse(entry_tapped('shock',0,True))
class SequencingTests(unittest.TestCase):
 def setUp(self):
  from material_opening_audit import MaterialPilot
  self.cards={'Forest':{'land':True,'model':'basic','colors':'G'},'Island':{'land':True,'model':'basic','colors':'U'},'Swamp':{'land':True,'model':'basic','colors':'B'},'Passage':{'land':True,'model':'passage','colors':''},'Tomb':{'land':True,'model':'shock','colors':'BG'},'Ant':{'land':False,'cost':'{G}{U}','mv':2,'body':True},'Maker':{'land':False,'cost':'{2}{G}','mv':3,'body':True,'tokens':1},'Jenova':{'land':False,'cost':'{2}{B}{G}','mv':4,'body':True,'anchor':True},'Recruit':{'land':False,'cost':'{G}','mv':1,'body':True,'offspring':True}}
  self.pilot=MaterialPilot(self.cards)
 def test_t1_fetch_no_missed_two_drop(self):
  r=self.pilot.play(['Passage','Tomb','Ant'],['Island','Forest'],turns=2,draw=False,remove=False)
  self.assertEqual(r['trace'][0]['fetch'],'Island');self.assertEqual(r['trace'][1]['casts'][0]['card'],'Ant');self.assertEqual(r['metrics']['shock_life'],2)
 def test_two_removals_still_leave_jenova_target(self):
  r=self.pilot.play(['Forest','Swamp','Forest','Forest','Recruit','Maker','Jenova'],[],draw=False,remove=True)
  self.assertEqual(r['metrics']['jenova_with_target'],1)
  self.assertEqual(r['trace'][2]['removed'],'Maker');self.assertEqual(len(r['trace'][2]['board']),1)
 def test_fourth_fetch_untapped(self):
  n,fetch,shock,tapped=self.pilot.choose(['Passage','Jenova'],['Forest','Forest','Swamp'],[],['Island'])
  self.assertEqual((n,fetch,tapped),('Passage','Island',False))
if __name__=='__main__':unittest.main()
