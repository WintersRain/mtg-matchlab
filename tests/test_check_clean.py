import unittest
from tools import check_clean as c

PATCH = '''diff --git a/forge-gui/res/a.txt b/forge-gui/res/a.txt
index 1..2 100644
--- a/forge-gui/res/a.txt
+++ b/forge-gui/res/a.txt
@@ -1 +1 @@
-x
+y
diff --git a/src/New.java b/src/New.java
new file mode 100644
--- /dev/null
+++ b/src/New.java
@@ -0,0 +1 @@
+class New {}
'''

class CheckCleanTests(unittest.TestCase):
    def test_patched_paths_include_modified_and_new_files(self):
        self.assertEqual(c.patched_paths(PATCH), {'forge-gui/res/a.txt', 'src/New.java'})

    def test_status_parsing(self):
        self.assertEqual(c.parse_status(' M a/b.txt\n?? c d.txt\n'), {'a/b.txt': 'M', 'c d.txt': '??'})

    def test_exactly_expected_changes_are_clean(self):
        status = {'forge-gui/res/a.txt': 'M', 'src/New.java': '??', 'res/upcoming/card.txt': '??'}
        self.assertEqual(c.classify(status, {'forge-gui/res/a.txt', 'src/New.java'}, {'res/upcoming/card.txt'}), [])

    def test_stray_engine_change_is_reported(self):
        status = {'forge-gui/res/a.txt': 'M', 'res/upcoming/handmade.txt': '??'}
        problems = c.classify(status, {'forge-gui/res/a.txt'}, set())
        self.assertEqual(problems, ['untracked engine change (not in patches/ or forge-resources/): res/upcoming/handmade.txt'])

    def test_missing_expected_changes_are_reported(self):
        problems = c.classify({}, {'forge-gui/res/a.txt'}, {'res/upcoming/card.txt'})
        self.assertEqual(problems, ['patched file not modified (patch not applied?): forge-gui/res/a.txt',
                                    'overlay not installed: res/upcoming/card.txt'])

if __name__ == '__main__':
    unittest.main()
