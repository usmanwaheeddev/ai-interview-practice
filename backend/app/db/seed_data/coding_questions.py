"""Seed data for the coding-challenge feature — plugged into `make seed` via
app/db/seed.py, not a separate seeding mechanism.

Java/C# starter code deliberately declares `class Solution` (Java: no
`public` modifier — Java requires the single `public` class in a file to
match its filename, and the generated driver claims that slot as
`public class Main`; see app/services/coding/harness.py). The function name
in each `function_signature` is shared verbatim across all three languages'
starter code, since the harness driver calls it identically regardless of
language — so method names here follow lowerCamelCase even in C#, rather
than the idiomatic PascalCase, to keep one signature source of truth.
"""

from app.db.models.coding import CodingDifficulty

CODING_QUESTIONS: list[dict] = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": CodingDifficulty.EASY,
        "description": (
            "Given an array of integers `nums` and an integer `target`, return the indices of "
            "the two numbers that add up to `target`.\n\n"
            "You may assume each input has exactly one solution, and you may not use the same "
            "element twice. Return the indices in any order."
        ),
        "constraints": [
            "2 <= nums.length <= 10^4",
            "-10^9 <= nums[i] <= 10^9",
            "-10^9 <= target <= 10^9",
            "Exactly one valid answer exists.",
        ],
        "examples": [
            {
                "input_display": "nums = [2,7,11,15], target = 9",
                "output_display": "[0,1]",
                "explanation": "nums[0] + nums[1] == 9, so return [0, 1].",
            },
            {
                "input_display": "nums = [3,2,4], target = 6",
                "output_display": "[1,2]",
                "explanation": None,
            },
        ],
        "class_name": "Solution",
        "function_signature": {
            "name": "twoSum",
            "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
            "return_type": "int[]",
        },
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def twoSum(self, nums, target):\n"
                "        # write your code here\n"
                "        pass\n"
            ),
            "java": (
                "class Solution {\n"
                "    public int[] twoSum(int[] nums, int target) {\n"
                "        // write your code here\n"
                "        return new int[]{};\n"
                "    }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public int[] twoSum(int[] nums, int target) {\n"
                "        // write your code here\n"
                "        return new int[]{};\n"
                "    }\n"
                "}\n"
            ),
        },
        "test_cases": {
            "sample": [
                ([[2, 7, 11, 15], 9], [0, 1]),
                ([[3, 2, 4], 6], [1, 2]),
                ([[3, 3], 6], [0, 1]),
            ],
            "hidden": [
                ([[1, 2, 3, 4, 5], 9], [3, 4]),
                ([[-3, 4, 3, 90], 0], [0, 2]),
                ([[5, 75, 25], 100], [1, 2]),
            ],
        },
    },
    {
        "slug": "reverse-string",
        "title": "Reverse String",
        "difficulty": CodingDifficulty.EASY,
        "description": (
            "Write a function that reverses a string `s`.\n\n"
            "Return the reversed string."
        ),
        "constraints": ["0 <= s.length <= 10^5"],
        "examples": [
            {"input_display": 's = "hello"', "output_display": '"olleh"', "explanation": None},
            {"input_display": 's = "a"', "output_display": '"a"', "explanation": None},
        ],
        "class_name": "Solution",
        "function_signature": {
            "name": "reverseString",
            "params": [{"name": "s", "type": "string"}],
            "return_type": "string",
        },
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def reverseString(self, s):\n"
                "        # write your code here\n"
                "        pass\n"
            ),
            "java": (
                "class Solution {\n"
                "    public String reverseString(String s) {\n"
                "        // write your code here\n"
                "        return \"\";\n"
                "    }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public string reverseString(string s) {\n"
                "        // write your code here\n"
                "        return \"\";\n"
                "    }\n"
                "}\n"
            ),
        },
        "test_cases": {
            "sample": [
                (["hello"], "olleh"),
                (["a"], "a"),
                (["ab"], "ba"),
            ],
            "hidden": [
                ([""], ""),
                (["racecar"], "racecar"),
                (["OpenAI"], "IAnepO"),
            ],
        },
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": CodingDifficulty.EASY,
        "description": (
            "Given a string `s` containing just the characters `(`, `)`, `{`, `}`, `[` and `]`, "
            "determine if the input string is valid.\n\n"
            "A string is valid if every open bracket is closed by the same type of bracket, and "
            "brackets close in the correct order."
        ),
        "constraints": ["1 <= s.length <= 10^4", "s consists only of bracket characters."],
        "examples": [
            {"input_display": 's = "()"', "output_display": "true", "explanation": None},
            {"input_display": 's = "(]"', "output_display": "false", "explanation": None},
        ],
        "class_name": "Solution",
        "function_signature": {
            "name": "isValid",
            "params": [{"name": "s", "type": "string"}],
            "return_type": "bool",
        },
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def isValid(self, s):\n"
                "        # write your code here\n"
                "        pass\n"
            ),
            "java": (
                "class Solution {\n"
                "    public boolean isValid(String s) {\n"
                "        // write your code here\n"
                "        return false;\n"
                "    }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public bool isValid(string s) {\n"
                "        // write your code here\n"
                "        return false;\n"
                "    }\n"
                "}\n"
            ),
        },
        "test_cases": {
            "sample": [
                (["()"], True),
                (["()[]{}"], True),
                (["(]"], False),
            ],
            "hidden": [
                (["([)]"], False),
                (["{[]}"], True),
                ([""], True),
            ],
        },
    },
    {
        "slug": "fizzbuzz",
        "title": "FizzBuzz",
        "difficulty": CodingDifficulty.EASY,
        "description": (
            "Given an integer `n`, return a string array `answer` (1-indexed) where:\n\n"
            "- `answer[i] == \"FizzBuzz\"` if `i` is divisible by 3 and 5.\n"
            "- `answer[i] == \"Fizz\"` if `i` is divisible by 3.\n"
            "- `answer[i] == \"Buzz\"` if `i` is divisible by 5.\n"
            "- `answer[i] == str(i)` otherwise."
        ),
        "constraints": ["0 <= n <= 10^4"],
        "examples": [
            {"input_display": "n = 3", "output_display": '["1","2","Fizz"]', "explanation": None},
            {
                "input_display": "n = 5",
                "output_display": '["1","2","Fizz","4","Buzz"]',
                "explanation": None,
            },
        ],
        "class_name": "Solution",
        "function_signature": {
            "name": "fizzBuzz",
            "params": [{"name": "n", "type": "int"}],
            "return_type": "string[]",
        },
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def fizzBuzz(self, n):\n"
                "        # write your code here\n"
                "        pass\n"
            ),
            "java": (
                "class Solution {\n"
                "    public String[] fizzBuzz(int n) {\n"
                "        // write your code here\n"
                "        return new String[]{};\n"
                "    }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public string[] fizzBuzz(int n) {\n"
                "        // write your code here\n"
                "        return new string[]{};\n"
                "    }\n"
                "}\n"
            ),
        },
        "test_cases": {
            "sample": [
                ([3], ["1", "2", "Fizz"]),
                ([5], ["1", "2", "Fizz", "4", "Buzz"]),
                ([1], ["1"]),
            ],
            "hidden": [
                (
                    [15],
                    [
                        "1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz",
                        "11", "Fizz", "13", "14", "FizzBuzz",
                    ],
                ),
                ([0], []),
                ([9], ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz"]),
            ],
        },
    },
    {
        "slug": "fibonacci-number",
        "title": "Fibonacci Number",
        "difficulty": CodingDifficulty.EASY,
        "description": (
            "The Fibonacci numbers, commonly denoted `F(n)`, form a sequence such that each "
            "number is the sum of the two preceding ones, starting from 0 and 1:\n\n"
            "F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2) for n > 1.\n\n"
            "Given `n`, calculate `F(n)`."
        ),
        "constraints": ["0 <= n <= 30"],
        "examples": [
            {
                "input_display": "n = 2",
                "output_display": "1",
                "explanation": "F(2) = F(1) + F(0) = 1.",
            },
            {"input_display": "n = 4", "output_display": "3", "explanation": None},
        ],
        "class_name": "Solution",
        "function_signature": {
            "name": "fib",
            "params": [{"name": "n", "type": "int"}],
            "return_type": "int",
        },
        "starter_code": {
            "python": (
                "class Solution:\n"
                "    def fib(self, n):\n"
                "        # write your code here\n"
                "        pass\n"
            ),
            "java": (
                "class Solution {\n"
                "    public int fib(int n) {\n"
                "        // write your code here\n"
                "        return 0;\n"
                "    }\n"
                "}\n"
            ),
            "csharp": (
                "public class Solution {\n"
                "    public int fib(int n) {\n"
                "        // write your code here\n"
                "        return 0;\n"
                "    }\n"
                "}\n"
            ),
        },
        "test_cases": {
            "sample": [
                ([2], 1),
                ([3], 2),
                ([4], 3),
            ],
            "hidden": [
                ([0], 0),
                ([1], 1),
                ([10], 55),
            ],
        },
    },
]
