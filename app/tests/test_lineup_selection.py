"""Regression: no credit for another starter as a hypothetical injury replacement."""
import importlib.util
import pathlib
import unittest
path = pathlib.Path(__file__).resolve().parents[2] / 'prototypes/start-sit/startsit.py'
spec = importlib.util.spec_from_file_location('lineup_engine', path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

class SelectionTests(unittest.TestCase):
    def test_questionable_backup_cannot_borrow_starting_rbs_points(self):
        players = [{'id':'gibbs','elig':['RB'],'value':24.3,'injury':None},
                   {'id':'swift','elig':['RB'],'value':15.1,'injury':None},
                   {'id':'price','elig':['RB'],'value':8.5,'injury':None},
                   {'id':'gordon','elig':['RB'],'value':6.4,'injury':'Questionable','play_prob':.5}]
        lineup = engine.choose_starters(['RB','RB','FLEX'], players)
        self.assertEqual({p['id'] for p in lineup}, {'gibbs','swift','price'})
        self.assertAlmostEqual(sum(p['value'] for p in lineup), 47.9)
    def test_selection_is_legal_and_each_player_used_once(self):
        players = [{'id':'qb','elig':['QB'],'value':25},
                   {'id':'rb','elig':['RB'],'value':20},
                   {'id':'te','elig':['TE'],'value':15},
                   {'id':'wr','elig':['WR'],'value':10}]
        slots = ['QB','RB','WR','TE','FLEX']
        lineup = engine.choose_starters(slots, players)
        used = [p['id'] for p in lineup if p]
        self.assertEqual(len(used),len(set(used)))
        self.assertTrue(all(p is None or engine.eligible(slot,p) for slot,p in zip(slots,lineup)))

if __name__ == '__main__': unittest.main()
