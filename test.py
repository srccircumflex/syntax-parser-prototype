import unittest

from demos.pysyntax import config, template


class MainTest(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

        self.m_config = config
        self.m_template = template

        with open(self.m_template.__file__) as f:
            self.original_content = f.read()
            self.root = self.m_config.main()
            self.result = self.root.parse_string(self.original_content)

        self.result_content = str().join(i.content for i in self.result.tokenReader.branch)

    def test_parsing(self):
        self.assertEqual(self.result_content, self.original_content)

    def test_reader(self):
        self.assertEqual(self.result.tokenReader.branch.content, self.original_content)

        all_tokens_linear = list(self.result.tokenReader.branch)
        self.assertEqual(all_tokens_linear, [self.result, *self.result.tokenReader.inner, self.result.end])

        self.assertEqual(list(reversed(all_tokens_linear)), list(self.result.tokenReader.branch(reverse=True)))
        self.assertEqual(all_tokens_linear, [*self.result.end.tokenReader.therebefore, self.result.end])

        def test_beyondreader(anchor):
            anchor_thereafter_content = str().join(str(i) for i in anchor.tokenReader.thereafter)
            self.assertEqual(self.original_content[anchor.data_end:], anchor_thereafter_content)

            anchor_therebefore_content = str().join(str(i) for i in anchor.tokenReader.therebefore)
            self.assertEqual(self.original_content[:anchor.data_start], anchor_therebefore_content)
            self.assertEqual(anchor_therebefore_content, anchor.tokenReader.therebefore.content)

        anchors = list(self.m_config.DEBUG_ANCHORS.values())
        for anchor in anchors:
            test_beyondreader(anchor)
            test_beyondreader(anchor.node)
            test_beyondreader(anchor.node.end)
            test_beyondreader(anchor.next)
            test_beyondreader(anchor.previous.node)
            test_beyondreader(anchor.previous.node.end)
            with self.assertRaises(EOFError):
                test_beyondreader(anchor.node.root)
            with self.assertRaises(EOFError):
                test_beyondreader(anchor.node.root.end)

    def test_content_replace(self):
        anchors = list(self.m_config.DEBUG_ANCHORS.values())
        main_content = self.original_content

        def replace_mirror(token, new_content):
            nonlocal main_content
            main_content = main_content[:token.data_start] + new_content + main_content[token.data_end:]
            token.replace_content(new_content)

        def test_new_places():
            for anchor in anchors:
                self.assertEqual(main_content[anchor.data_start:anchor.data_end], anchor.content)

        test_new_places()

        new_contents = [
            "¿new1",
            "¿" * 20,
            "",
            "new4¿",
            "",
        ]
        from secrets import choice
        from random import shuffle

        for i in range(5):
            replace_mirror(choice(anchors), choice(new_contents))
            test_new_places()

        for i in range(5):
            shuffle(anchors)
            shuffle(new_contents)
            for a, n in zip(anchors, new_contents):
                replace_mirror(a, n)

        test_new_places()

        for i in range(5):
            shuffle(anchors)
            shuffle(new_contents)
            for a, n in zip(anchors, new_contents):
                for a in (a.node, a.node.end, a.next, a.previous.node, a.previous.node.end):
                    replace_mirror(a, n)

        test_new_places()


if __name__ == '__main__':
    unittest.main()
