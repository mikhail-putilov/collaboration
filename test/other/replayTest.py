from other import compute_delay

__author__ = 'snowy'

import unittest


class MyTestCase(unittest.TestCase):
    def test_compute_delay(self):
        stash = [(1422191569.3800001, 'repla\nHe'), (1422191569.6700001, 'repla\nHell'), (1422191569.9300001, 'repla\nHello '), (1422191570.73, 'repla\nHello wo'), (1422191570.9200001, 'repla\nHello worl'), (1422191571.29, 'repla\nHello world!\n')]
        delayed = compute_delay(stash)
        for i, (s, d) in enumerate(zip(stash[:-1], delayed[:-1])):
            self.assertEqual(s[1], d[1])
            self.assertAlmostEqual(s[0]+d[0], stash[i+1][0], delta=0.1)


if __name__ == '__main__':
    unittest.main()
