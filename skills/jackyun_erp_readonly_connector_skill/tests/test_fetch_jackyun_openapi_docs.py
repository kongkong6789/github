import unittest

from scripts.fetch_jackyun_openapi_docs import build_method_summary, parse_method_from_url


class TestFetchJackyunOpenapiDocs(unittest.TestCase):
    def test_parse_method_from_url(self):
        url = "https://open.jackyun.com/developer/apidocinfo.html?from=self&value=undefined&id=erp.allocate.create&name=true"
        self.assertEqual(parse_method_from_url(url), "erp.allocate.create")

    def test_build_method_summary(self):
        payload = {
            "result": {
                "data": {
                    "docEntity": {
                        "method": "erp.allocate.create",
                        "name": "调拨单创建",
                        "directoryCode": "erp",
                        "remark": "备注",
                        "dataVersion": "2026-04-14",
                        "bAuthorized": True,
                    },
                    "docParameterInfos": [
                        {
                            "fullParameterName": "stockAllocateExpressInfo-send",
                            "parameterName": "send",
                            "parentName": "stockAllocateExpressInfo",
                            "dataType": "String",
                            "bRequired": False,
                            "remark": "发件人",
                            "demoValue": "张三",
                            "bRequest": True,
                        },
                        {
                            "fullParameterName": "result-code",
                            "parameterName": "code",
                            "parentName": "result",
                            "dataType": "String",
                            "bRequired": False,
                            "remark": "状态码",
                            "demoValue": "200",
                            "bRequest": False,
                        },
                    ],
                }
            }
        }
        summary = build_method_summary(payload)
        self.assertEqual(summary["method"], "erp.allocate.create")
        self.assertEqual(len(summary["request_params"]), 1)
        self.assertEqual(summary["request_params"][0]["parameter_name"], "send")
        self.assertEqual(len(summary["response_params"]), 1)


if __name__ == "__main__":
    unittest.main()
