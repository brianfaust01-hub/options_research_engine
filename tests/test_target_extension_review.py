import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from target_extension_review import intervention_index, replay, rising, rules


class TargetExtensionTests(unittest.TestCase):
    @staticmethod
    def points(*bids):
        return [(i*60, i*60, bid, bid+.02) for i, bid in enumerate(bids)]

    def rule(self, lock=None, gate='always'):
        return dict(activation=.75, multiple=1.5, lock=lock, gate=gate)

    def test_existing_target_can_fill_during_replacement_delay(self):
        value = replay(self.points(11.6, 12.2, 13.2), 10, 1, 8, 12,
                       self.rule(), 60, .01)
        self.assertFalse(value['active'])
        self.assertEqual(value['fills'][0][1:], (12, 1, 'target'))

    def test_extension_captures_higher_target_after_activation(self):
        value = replay(self.points(11.6, 11.7, 12.2, 13.2), 10, 1, 8, 12,
                       self.rule(), 60, .01)
        self.assertTrue(value['active'])
        self.assertEqual(value['fills'][0][1:], (13, 1, 'target'))

    def test_protected_extension_can_surrender_original_target_gain(self):
        value = replay(self.points(11.6, 12.2, 11.0), 10, 1, 8, 12,
                       self.rule(.75), 0, .01)
        self.assertEqual(value['fills'][-1][1:], (10.99, 1, 'stop'))

    def test_rising_gate_uses_only_prior_quotes(self):
        points = self.points(11.6, 11.5, 11.4, 11.3, 20)
        self.assertFalse(rising(points, 3, .01))
        self.assertTrue(rising(points, 4, .01))

    def test_stop_fill_does_not_recover_to_target_after_partial_fill(self):
        value = replay(self.points(7, 13.2, 13.2), 10, 3, 8, 12,
                       self.rule(), 0, .01, 1)
        self.assertEqual([f[3] for f in value['fills']], ['stop']*3)
        self.assertEqual(sum(f[2] for f in value['fills']), 3)

    def test_untriggered_rule_equals_original(self):
        points = self.points(10, 10.5, 9.5)
        original = rules()[0]
        self.assertEqual(replay(points, 10, 2, 8, 12, original, 60, .01),
                         replay(points, 10, 2, 8, 12, self.rule(), 60, .01))

    def test_protection_survives_lower_broker_stop_amendment(self):
        value = replay(self.points(11.6, 12.2, 11), 10, 1, 8, 12,
                       self.rule(.75), 0, .01, amendments=[(120, 1, 'STP', 7)])
        self.assertEqual(value['fills'][0][3], 'stop')

    def test_stale_signal_rechecked_when_delay_ends(self):
        value = replay(self.points(11.6, 11.2, 12.2), 10, 1, 8, 12,
                       self.rule(), 60, .01)
        self.assertFalse(value['active'])
        self.assertEqual(value['fills'][0][1], 12)

    def test_actual_intervention_requires_change_before_actual_sale(self):
        rule = dict(activation=.75, multiple=1.5, lock=None, gate='always')
        points = self.points(10, 11.6, 12.2)
        self.assertIsNone(intervention_index(points, 10, 1, 8, 12, rule, 60, .01, 120, []))
        self.assertEqual(intervention_index(points, 10, 1, 8, 12, rule, 0, .01, 120, []), 1)

    def test_intervention_starts_from_actual_intact_position(self):
        rule = dict(activation=.75, multiple=1.5, lock=None, gate='always')
        points = self.points(7, 11.6, 12.2, 13.1)
        index = intervention_index(points, 10, 1, 8, 12, rule, 0, .01, 120, [])
        self.assertEqual(index, 1)
        result = replay(points, 10, 1, 8, 12, rule, 0, .01, start_index=index)
        self.assertEqual(result['fills'][0][1], 13)


if __name__ == '__main__':
    unittest.main()
