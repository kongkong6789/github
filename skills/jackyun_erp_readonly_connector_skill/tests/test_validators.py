"""
验证器单元测试
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.validators import (
    require_fields,
    require_fields_or_raise,
    validate_phone,
    validate_amount,
    validate_quantity,
    validate_date_str,
    validate_datetime_str,
    format_missing_fields_prompt,
)
from jackyun_api import JackyunValidationError


class TestRequireFields(unittest.TestCase):

    def test_all_present(self):
        """所有必填字段都存在"""
        data = {"a": 1, "b": "hello", "c": [1, 2]}
        fields = [("a", "字段A"), ("b", "字段B"), ("c", "字段C")]
        missing = require_fields(data, fields)
        self.assertEqual(missing, [])

    def test_missing_one(self):
        """缺少一个字段"""
        data = {"a": 1}
        fields = [("a", "字段A"), ("b", "字段B")]
        missing = require_fields(data, fields)
        self.assertIn("字段B", missing)

    def test_empty_value(self):
        """空字符串视为缺失"""
        data = {"a": "", "b": "ok"}
        fields = [("a", "字段A"), ("b", "字段B")]
        missing = require_fields(data, fields)
        self.assertIn("字段A", missing)

    def test_raise_on_missing(self):
        """缺少字段时抛出异常"""
        data = {"a": 1}
        fields = [("a", "字段A"), ("b", "字段B")]
        with self.assertRaises(JackyunValidationError) as ctx:
            require_fields_or_raise(data, fields)
        self.assertIn("字段B", str(ctx.exception))


class TestValidatePhone(unittest.TestCase):

    def test_valid_phone(self):
        self.assertTrue(validate_phone("13800138000"))
        self.assertTrue(validate_phone("19912345678"))

    def test_invalid_phone(self):
        self.assertFalse(validate_phone("1380013"))
        self.assertFalse(validate_phone("abc"))


class TestValidateAmount(unittest.TestCase):

    def test_valid_amounts(self):
        self.assertTrue(validate_amount(100))
        self.assertTrue(validate_amount(0.01))
        self.assertTrue(validate_amount("99.9"))
        self.assertTrue(validate_amount(0))

    def test_invalid_amounts(self):
        self.assertFalse(validate_amount(-1))
        self.assertFalse(validate_amount("abc"))


class TestValidateQuantity(unittest.TestCase):

    def test_valid(self):
        self.assertTrue(validate_quantity(1))
        self.assertTrue(validate_quantity(100))

    def test_invalid(self):
        self.assertFalse(validate_quantity(0))
        self.assertFalse(validate_quantity(-5))
        self.assertFalse(validate_quantity("abc"))


class TestValidateDate(unittest.TestCase):

    def test_valid_dates(self):
        self.assertTrue(validate_date_str("2024-01-01"))
        self.assertTrue(validate_date_str("2024-12-31"))

    def test_valid_datetime(self):
        self.assertTrue(validate_datetime_str("2024-12-31 23:59:59"))

    def test_invalid_dates(self):
        self.assertFalse(validate_date_str("not-a-date"))


class TestMissingFieldsPrompt(unittest.TestCase):

    def test_generates_prompt(self):
        missing = ["收件人姓名", "收件人电话"]
        prompt = format_missing_fields_prompt(missing)
        self.assertIn("收件人姓名", prompt)
        self.assertIn("收件人电话", prompt)


if __name__ == "__main__":
    unittest.main()
