import io
import json
import unittest
from unittest.mock import patch

from blackserv_coder.evaluate import choose_tool, evaluate


class EvaluationTests(unittest.TestCase):
    def test_choice_extraction(self):
        self.assertIsNone(choose_tool({"content":"No call"}))
        self.assertEqual(choose_tool({"tool_calls":[{"function":{"name":"read_file"}}]}),
                         "read_file")

    def test_benchmark_does_not_execute_tools(self):
        body={"choices":[{"message":{"tool_calls":[{"function":{"name":"list_files"}}]}}],
              "usage":{"total_tokens":20}}
        stub=io.BytesIO(json.dumps(body).encode("utf-8"))
        with patch("blackserv_coder.evaluate.request.urlopen",return_value=stub) as mock:
            result=evaluate("http://localhost:8080/v1",
                            [{"id":"list","prompt":"List workspace","tool":"list_files"}])
        self.assertEqual(len(result),1)
        self.assertTrue(result[0]["pass"])
        self.assertEqual(result[0]["usage"]["total_tokens"],20)
        request=mock.call_args.args[0]
        payload=json.loads(request.data)
        self.assertEqual(payload["tool_choice"],"auto")
        self.assertTrue(payload["tools"])


if __name__=="__main__":
    unittest.main()
