"""Stage 6 (71-88): strings."""

import string

from .base import NAMES, WORDS, Spec

SENTENCES = [
    "India won the match by six wickets",
    "my mother makes the best rasam in town",
    "practice every day to become a great coder",
    "the quick brown fox jumps over the lazy dog",
    "Mumbai local trains are always crowded",
    "Learning to code is like learning to ride a cycle",
    "chai tastes better when it is raining",
    "Never give up on your dreams",
    "Bengaluru traffic tests the patience of everyone",
    "Coding is fun when you understand the logic",
    "A journey of a thousand miles begins with a single step",
    "keep calm and write clean code",
]


def _sentence(r, words=None):
    words = words or WORDS
    return " ".join(r.choice(words) for _ in range(r.randint(1, 8)))


def _mixed_sentence(r):
    if r.random() < 0.4:
        return r.choice(SENTENCES)
    return " ".join(w.capitalize() if r.random() < 0.3 else w for w in _sentence(r).split())


def _word(r, lo=1, hi=12, alphabet=string.ascii_lowercase):
    return "".join(r.choice(alphabet) for _ in range(r.randint(lo, hi)))


def _palindrome_case(r):
    if r.random() < 0.5:
        half = _word(r, 1, 6, "abcde")
        word = half + (half[-2::-1] if r.random() < 0.5 else half[::-1])
    else:
        word = _word(r, 1, 8, "abc")
    return "".join(c.upper() if r.random() < 0.3 else c for c in word)


def _anagram_case(r):
    a = _word(r, 1, 10, "abcdefg")
    if r.random() < 0.5:
        b = "".join(r.sample(a, len(a)))
    else:
        b = list(a)
        b[r.randrange(len(b))] = r.choice("abcdefgh")
        r.shuffle(b)
        b = "".join(b)
    return f"{a}\n{b}"


def _spaced_sentence(r):
    words = [r.choice(WORDS) for _ in range(r.randint(1, 8))]
    return "".join(w + (" " * r.randint(1, 3) if i < len(words) - 1 else "") for i, w in enumerate(words))


def _password(r):
    pool = string.ascii_letters + string.digits + "!@#$%&*_-?"
    pw = "".join(r.choice(pool) for _ in range(r.randint(4, 14)))
    return pw


def _brackets(r):
    if r.random() < 0.5:
        # build a valid one
        s, stack = "", []
        for _ in range(r.randint(1, 10)):
            if stack and r.random() < 0.5:
                s += {"(": ")", "[": "]", "{": "}"}[stack.pop()]
            else:
                o = r.choice("([{")
                stack.append(o)
                s += o
        while stack:
            s += {"(": ")", "[": "]", "{": "}"}[stack.pop()]
        return s
    return "".join(r.choice("()[]{}") for _ in range(r.randint(1, 14)))


def _prefix_case(r):
    stem = _word(r, 0, 5, "abc")
    words = [stem + _word(r, 0, 4, "abcd") for _ in range(r.randint(1, 5))]
    words = [w if w else "a" for w in words]
    return f"{len(words)}\n" + "\n".join(words)


def _caesar(r):
    return f"{_sentence(r)}\n{r.randint(0, 1000)}"


SPECS = [
    Spec(
        slug="count-vowels-in-a-sentence",
        title="Count the Vowels",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "A Tamil teacher says English words feel 'soft' when they have many vowels. "
            "Given a sentence, count how many vowels (a, e, i, o, u in small or capital letters) it has."
        ),
        input_format="A single line containing a sentence (letters and spaces).",
        output_format="Print the number of vowels.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=["Loop over every character of the string.", "Convert each character to lowercase and check whether it is in \"aeiou\"."],
        approach=(
            "Strings are just arrays of characters, so the same scan-and-count pattern works. "
            "Lowercasing each character means you only compare against five vowels.\n\n"
            "Note: reading a full line with spaces needs getline in C++ or nextLine in Java."
        ),
        time="O(length)", space="O(1)",
        solution='''
s = input()
count = 0
for ch in s:
    if ch.lower() in "aeiou":
        count += 1
print(count)
''',
        samples=[
            ("India won the match", "I, i, a, o, e, a: 6 vowels."),
            ("rhythm", "No vowels at all."),
            ("AEIOU aeiou", "All 10 are vowels, both cases count."),
        ],
        edge=["a", "b", "Sky by my gym", "Education Is Our Future"],
        gen=_mixed_sentence,
    ),
    Spec(
        slug="reverse-a-message",
        title="Secret Mirror Message",
        difficulty="easy",
        tags=["Strings", "Two Pointers"],
        story=(
            "Two friends send secret messages by writing them backwards. "
            "Given a message, print it reversed, character by character (spaces included)."
        ),
        input_format="A single line containing the message.",
        output_format="Print the reversed message.",
        constraints=["1 ≤ length ≤ 1000", "The message has letters and spaces, and does not start or end with a space."],
        hints=["Loop from the last index down to 0.", "In Python, s[::-1] reverses a string, but try writing the loop yourself first."],
        approach=(
            "Same as reversing an array: read characters from the end to the start. "
            "In languages where strings can't be changed, build a new string, or use a character array and swap with two pointers."
        ),
        time="O(length)", space="O(length)",
        solution='''
s = input()
result = ""
for i in range(len(s) - 1, -1, -1):
    result += s[i]
print(result)
''',
        samples=[
            ("hello world", "Read from right to left."),
            ("abc", "c, b, a."),
            ("Madam", "Capital M moves to the end."),
        ],
        edge=["a", "ab", "Never give up", "racecar"],
        gen=_mixed_sentence,
    ),
    Spec(
        slug="palindrome-word",
        title="Palindrome Word",
        difficulty="easy",
        tags=["Strings", "Two Pointers"],
        story=(
            "Words like 'Malayalam', 'level' and 'Madam' read the same forwards and backwards. These are palindromes.\n\n"
            "Given a word, check whether it is a palindrome, ignoring the difference between capital and small letters."
        ),
        input_format="A single word.",
        output_format="Print Palindrome or Not Palindrome.",
        constraints=["1 ≤ length ≤ 1000", "The word contains only English letters."],
        hints=["Lowercase the word first.", "Compare s[i] with s[n - 1 - i] for i in the first half."],
        approach=(
            "Two pointers, one from each end. If any pair of characters differs, it's not a palindrome. "
            "You only need to check half of the word.\n\n"
            "Lowercasing first handles inputs like 'Malayalam'."
        ),
        time="O(length)", space="O(1)",
        solution='''
s = input().strip().lower()
left, right = 0, len(s) - 1
ok = True
while left < right:
    if s[left] != s[right]:
        ok = False
        break
    left += 1
    right -= 1
print("Palindrome" if ok else "Not Palindrome")
''',
        samples=[
            ("Malayalam", "malayalam reads the same both ways."),
            ("coder", "coder reversed is redoc."),
            ("a", "A single letter is always a palindrome."),
            ("Noon", "noon is a palindrome."),
        ],
        edge=["ab", "aa", "abca", "racecar", "Level", "abcdba"],
        gen=_palindrome_case,
    ),
    Spec(
        slug="word-counter",
        title="Word Counter",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "An essay competition has a word limit. The judges' software must count the words in each line.\n\n"
            "Words are separated by one or more spaces. Count the words."
        ),
        input_format="A single line. It does not start or end with a space, but there may be several spaces between words.",
        output_format="Print the number of words.",
        constraints=["1 ≤ length ≤ 1000", "The line has at least one word."],
        hints=[
            "Counting spaces fails when there are double spaces.",
            "Count positions where a non-space character starts a word: s[i] != ' ' and (i == 0 or s[i-1] == ' ').",
        ],
        approach=(
            "A word begins wherever a non-space character comes after a space (or at the very start). Count those beginnings.\n\n"
            "In Python, len(s.split()) does the same, because split() with no argument treats any run of spaces as one separator."
        ),
        time="O(length)", space="O(1)",
        solution='''
s = input()
count = 0
for i in range(len(s)):
    if s[i] != " " and (i == 0 or s[i - 1] == " "):
        count += 1
print(count)
''',
        samples=[
            ("I love coding", "Three words."),
            ("hello    world", "Many spaces, but still only two words."),
            ("BashaByte", "A single word."),
        ],
        edge=["a", "a b", "a  b  c  d", "one two three four five six seven"],
        gen=_spaced_sentence,
    ),
    Spec(
        slug="toggle-the-case",
        title="Caps Lock Accident",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "Karthik typed his message with Caps Lock on by mistake. Fix it by swapping the case of every letter: "
            "capital letters become small and small letters become capital. Other characters stay the same."
        ),
        input_format="A single line of text.",
        output_format="Print the text with the case of every letter swapped.",
        constraints=["1 ≤ length ≤ 1000", "The line does not start or end with a space."],
        hints=[
            "Check each character: if it is uppercase, convert it to lowercase, and vice versa.",
            "In ASCII, 'a' - 'A' = 32. Adding or subtracting 32 switches the case.",
        ],
        approach=(
            "Go character by character, and change only letters. "
            "Digits, spaces and symbols must pass through untouched, which is the detail people miss."
        ),
        time="O(length)", space="O(length)",
        solution='''
s = input()
result = ""
for ch in s:
    if "A" <= ch <= "Z":
        result += ch.lower()
    elif "a" <= ch <= "z":
        result += ch.upper()
    else:
        result += ch
print(result)
''',
        samples=[
            ("hELLO wORLD", "Every letter flips: Hello World."),
            ("Room 101", "The digits and the space stay the same."),
            ("BASHABYTE", "All capitals become small."),
        ],
        edge=["a", "Z", "123", "MiXeD CaSe 2024!"],
        gen=_mixed_sentence,
    ),
    Spec(
        slug="headline-title-case",
        title="Newspaper Headline",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "The newspaper editor wants every headline in Title Case: the first letter of each word capital, and the rest small.\n\n"
            "Given a headline, convert it to Title Case."
        ),
        input_format="A single line of words (letters only) separated by single spaces.",
        output_format="Print the headline in Title Case.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=["Split the line into words.", "For each word: word[0].upper() + word[1:].lower()."],
        approach=(
            "Process word by word: capitalise the first character and lowercase the rest, then join the words back with single spaces.\n\n"
            "Don't forget to lowercase the rest, because the input may contain random capitals."
        ),
        time="O(length)", space="O(length)",
        solution='''
words = input().split()
result = []
for w in words:
    result.append(w[0].upper() + w[1:].lower())
print(" ".join(result))
''',
        samples=[
            ("india wins the world cup", "Each word starts with a capital."),
            ("hELLO cHENNAI", "The rest of each word is made small."),
            ("a", "A single letter becomes A."),
        ],
        edge=["x y z", "ALL CAPS HEADLINE", "already Title Case"],
        gen=lambda r: " ".join(
            "".join(c.upper() if r.random() < 0.3 else c for c in w) for w in _sentence(r).split()
        ),
    ),
    Spec(
        slug="letter-frequency",
        title="Letter Frequency",
        difficulty="easy",
        tags=["Strings", "Hashing"],
        story=(
            "A Scrabble player wants to know how many times each letter appears in a word.\n\n"
            "Print every letter present, with its count, in alphabetical order."
        ),
        input_format="A single word in lowercase letters.",
        output_format="For each letter that appears, in alphabetical order, print a line: <letter> <count>",
        constraints=["1 ≤ length ≤ 1000"],
        hints=[
            "Use an array of 26 counters, one per letter. The index is ord(ch) - ord('a').",
            "Then print counters 0 to 25 that are above zero.",
        ],
        approach=(
            "A fixed array of 26 counts is the classic way to count letters. Each letter maps to an index using character arithmetic.\n\n"
            "Walking the array from 0 to 25 automatically gives alphabetical order, so no sorting is needed."
        ),
        time="O(length)", space="O(26)",
        solution='''
s = input().strip()
counts = [0] * 26
for ch in s:
    counts[ord(ch) - ord("a")] += 1
for i in range(26):
    if counts[i] > 0:
        print(chr(ord("a") + i), counts[i])
''',
        samples=[
            ("banana", "a appears 3 times, b once and n twice."),
            ("zebra", "Every letter once, printed in a to z order."),
            ("aaaa", "Only a, 4 times."),
        ],
        edge=["a", "z", "abcdefghijklmnopqrstuvwxyz", "mississippi"],
        gen=lambda r: _word(r, 1, 20, "abcdefghij"),
    ),
    Spec(
        slug="first-unique-character",
        title="First Unique Character",
        difficulty="medium",
        tags=["Strings", "Hashing"],
        story=(
            "In a lucky draw, the first participant whose name initial is not shared with anyone else wins.\n\n"
            "Given a string of initials, find the index (0-based) of the first character that appears exactly once. If none exists, print -1."
        ),
        input_format="A single string of lowercase letters.",
        output_format="Print the index of the first non-repeating character, or -1.",
        constraints=["1 ≤ length ≤ 10^5"],
        hints=["First pass: count every character.", "Second pass: return the first index whose count is 1."],
        approach=(
            "You can't decide on the first pass whether a character repeats later. So count everything first, then scan again in order.\n\n"
            "Two passes with a frequency table is O(n), compared with O(n²) for checking each character against all others. "
            "This is LeetCode #387."
        ),
        time="O(n)", space="O(26)",
        solution='''
s = input().strip()
counts = {}
for ch in s:
    counts[ch] = counts.get(ch, 0) + 1
answer = -1
for i in range(len(s)):
    if counts[s[i]] == 1:
        answer = i
        break
print(answer)
''',
        samples=[
            ("leetcode", "l appears only once and comes first, so index 0."),
            ("loveleetcode", "v at index 2 is the first unique character."),
            ("aabb", "Every character repeats."),
        ],
        edge=["z", "zz", "abcabcd", "aabbccddeeffg"],
        gen=lambda r: _word(r, 1, 15, "abcdef"),
    ),
    Spec(
        slug="anagram-check",
        title="Are They Anagrams?",
        difficulty="easy",
        tags=["Strings", "Hashing", "Sorting"],
        story=(
            "'listen' and 'silent' use exactly the same letters, just rearranged. Such words are anagrams.\n\n"
            "Given two words, check whether they are anagrams of each other."
        ),
        input_format="The first line has word s.\nThe second line has word t.\nBoth are lowercase.",
        output_format="Print Yes if they are anagrams, otherwise No.",
        constraints=["1 ≤ length of s, t ≤ 10^5"],
        hints=[
            "If the lengths differ, the answer is immediately No.",
            "Compare letter counts (26 counters), or sort both words and compare.",
        ],
        approach=(
            "Two words are anagrams exactly when every letter appears the same number of times in both. "
            "Count with s and uncount with t. If every counter ends at zero, they match.\n\n"
            "Sorting both and comparing also works in O(n log n). This is LeetCode #242."
        ),
        time="O(n)", space="O(26)",
        solution='''
s = input().strip()
t = input().strip()
if len(s) != len(t):
    print("No")
else:
    counts = [0] * 26
    for ch in s:
        counts[ord(ch) - ord("a")] += 1
    for ch in t:
        counts[ord(ch) - ord("a")] -= 1
    print("Yes" if all(c == 0 for c in counts) else "No")
''',
        samples=[
            ("listen\nsilent", "Same letters, different order."),
            ("rat\ncar", "rat has t but car has c."),
            ("aab\nabb", "Same letters, but different counts."),
        ],
        edge=["a\na", "a\nb", "ab\nabc", "abc\ncba", "aaaa\naaaa"],
        gen=_anagram_case,
    ),
    Spec(
        slug="remove-the-vowels",
        title="SMS Shortcut (Remove Vowels)",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "In the old days of SMS, people saved characters by dropping vowels: 'message' became 'mssg'.\n\n"
            "Remove all vowels (a, e, i, o, u in both cases) from the given text."
        ),
        input_format="A single line of text.",
        output_format="Print the text without vowels. Spaces and other characters stay as they are.",
        constraints=["1 ≤ length ≤ 1000", "The text has at least one character that is not a vowel or a space."],
        hints=[
            "Build a new string and add every character that is not a vowel.",
            "Compare ch.lower() against \"aeiou\" so capital vowels are removed too.",
        ],
        approach=(
            "Filter the characters: keep a character only if its lowercase form isn't in \"aeiou\".\n\n"
            "Building a new string from selected characters is a very common string technique."
        ),
        time="O(length)", space="O(length)",
        solution='''
s = input()
result = ""
for ch in s:
    if ch.lower() not in "aeiou":
        result += ch
print(result)
''',
        samples=[
            ("see you at the station", "Every a, e, i, o and u is dropped. The spaces stay where they were."),
            ("BashaByte", "Capital and small vowels are both removed."),
            ("rhythm", "Nothing to remove."),
        ],
        edge=["b", "Programming Is Fun", "xyz abc"],
        gen=lambda r: _mixed_sentence(r) + " " + r.choice(["now", "ok", "bye", "thx"]),
    ),
    Spec(
        slug="longest-word",
        title="Longest Word in the Sentence",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "During a spelling bee, the judge picks the longest word from a sentence.\n\n"
            "Print the longest word. If several words share the greatest length, print the one that appears first."
        ),
        input_format="A single line of words separated by single spaces.",
        output_format="Print the longest word.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=["Split into words and track the best word so far.", "Update only when a word is strictly longer, so the first one wins ties."],
        approach=(
            "Same 'best so far' scan as finding a maximum, but comparing lengths. "
            "Using > instead of >= keeps the earliest word on a tie, so small operator choices matter."
        ),
        time="O(length)", space="O(length)",
        solution='''
words = input().split()
best = words[0]
for w in words:
    if len(w) > len(best):
        best = w
print(best)
''',
        samples=[
            ("I love eating masala dosa", "eating and masala both have 6 letters. eating comes first."),
            ("Programming is fun", "Programming is clearly the longest."),
            ("hi", "Only one word."),
        ],
        edge=["a", "ab cd", "a bb ccc dd e", "same size word"],
        gen=lambda r: _sentence(r),
    ),
    Spec(
        slug="string-compression",
        title="String Compression",
        difficulty="easy",
        tags=["Strings", "Two Pointers"],
        story=(
            "To save space, a sensor stores repeated readings in short form: 'aaabbc' becomes 'a3b2c1'.\n\n"
            "Compress the string by writing each group of the same character followed by its count."
        ),
        input_format="A single string of lowercase letters.",
        output_format="Print the compressed string.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=[
            "Walk through the string, counting how long the current run of the same character is.",
            "When the character changes (or the string ends), write the character and its count.",
        ],
        approach=(
            "Process runs of equal characters. A run ends when the next character is different or there is no next character. "
            "That's when you add the letter and its count to the answer.\n\n"
            "This is also called run-length encoding, and it is used in real image formats."
        ),
        time="O(length)", space="O(length)",
        solution='''
s = input().strip()
result = ""
i = 0
while i < len(s):
    j = i
    while j < len(s) and s[j] == s[i]:
        j += 1
    result += s[i] + str(j - i)
    i = j
print(result)
''',
        samples=[
            ("aaabbc", "Three a's, two b's and one c."),
            ("abc", "No repeats, so each count is 1."),
            ("zzzzzzzzzzzz", "Twelve z's become z12."),
        ],
        edge=["a", "aa", "abab", "aabbaa"],
        gen=lambda r: "".join(r.choice("abc") * r.randint(1, 5) for _ in range(r.randint(1, 6))),
    ),
    Spec(
        slug="caesar-cipher",
        title="Caesar's Secret Code",
        difficulty="easy",
        tags=["Strings", "Math"],
        story=(
            "Julius Caesar sent secret messages by shifting every letter forward by k places in the alphabet. "
            "After z, it wraps around to a.\n\n"
            "With k = 3: a → d, x → a, z → c. Spaces stay as they are. Encode the message."
        ),
        input_format="The first line has the message (lowercase letters and spaces).\nThe second line has k.",
        output_format="Print the encoded message.",
        constraints=["1 ≤ length ≤ 1000", "0 ≤ k ≤ 1000"],
        hints=[
            "Convert a letter to a number 0-25, add k, take % 26, and convert back.",
            "new = chr((ord(ch) - ord('a') + k) % 26 + ord('a'))",
        ],
        approach=(
            "Map each letter to 0-25, shift it, and use % 26 to wrap around. "
            "Reducing k with % 26 means even k = 1000 works without any loops.\n\n"
            "This combines character arithmetic with modulo, the same wrap-around idea as array rotation."
        ),
        time="O(length)", space="O(length)",
        solution='''
s = input()
k = int(input())
result = ""
for ch in s:
    if ch == " ":
        result += " "
    else:
        result += chr((ord(ch) - ord("a") + k) % 26 + ord("a"))
print(result)
''',
        samples=[
            ("hello world\n3", "Each letter moves 3 steps: h → k, e → h, and so on."),
            ("xyz\n3", "x → a, y → b, z → c (wrapping around)."),
            ("abc\n26", "Shifting by 26 is a full circle, so no change."),
        ],
        edge=["a\n0", "z\n1", "zebra\n1000", "attack at dawn\n13"],
        gen=_caesar,
    ),
    Spec(
        slug="reverse-the-words",
        title="Reverse the Words",
        difficulty="easy",
        tags=["Strings", "Two Pointers"],
        story=(
            "Yoda from Star Wars speaks in reverse order, he does. Turn a normal sentence into Yoda-speak by reversing the order of the words "
            "(not the letters)."
        ),
        input_format="A single line of words separated by single spaces.",
        output_format="Print the words in reverse order, separated by single spaces.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=["Split into a list of words.", "Reverse the list (two pointers again!) and join with spaces."],
        approach=(
            "Split the sentence into words, reverse the list, and join it back. Each word itself stays the same.\n\n"
            "This is the array-reversal problem in disguise, at the word level. Compare it with reversing characters."
        ),
        time="O(length)", space="O(length)",
        solution='''
words = input().split()
left, right = 0, len(words) - 1
while left < right:
    words[left], words[right] = words[right], words[left]
    left += 1
    right -= 1
print(" ".join(words))
''',
        samples=[
            ("i love chai", "The last word comes first. Each word itself is not reversed."),
            ("BashaByte", "One word stays the same."),
            ("one two three four", "Four words in the opposite order."),
        ],
        edge=["a b", "a", "practice makes a coder perfect"],
        gen=_mixed_sentence,
    ),
    Spec(
        slug="pangram-check",
        title="Pangram Checker",
        difficulty="easy",
        tags=["Strings", "Hashing"],
        story=(
            "A pangram is a sentence that uses every letter of the English alphabet at least once, "
            "like 'The quick brown fox jumps over the lazy dog'. Typists use them to test keyboards.\n\n"
            "Check whether the given sentence is a pangram (ignore case)."
        ),
        input_format="A single line of letters and spaces.",
        output_format="Print Pangram or Not Pangram.",
        constraints=["1 ≤ length ≤ 1000"],
        hints=["Keep 26 boolean flags (or a set) and mark each letter you see.", "At the end, check that all 26 are marked."],
        approach=(
            "Mark letters as seen, ignoring case and spaces. If the number of distinct letters reaches 26, it's a pangram.\n\n"
            "A set or a boolean array of size 26 is all the memory you need, whatever the sentence length."
        ),
        time="O(length)", space="O(26)",
        solution='''
s = input().lower()
seen = set()
for ch in s:
    if "a" <= ch <= "z":
        seen.add(ch)
print("Pangram" if len(seen) == 26 else "Not Pangram")
''',
        samples=[
            ("The quick brown fox jumps over the lazy dog", "All 26 letters are used."),
            ("Hello world", "Many letters are missing, like a, b and c."),
            ("Pack my box with five dozen liquor jugs", "Another famous pangram."),
        ],
        edge=["abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXY", "a",
              "Sphinx of black quartz judge my vow", "The quick brown fox jumps over the lay dog"],
        gen=_mixed_sentence,
    ),
    Spec(
        slug="password-strength",
        title="Password Strength Checker",
        difficulty="easy",
        tags=["Strings", "Conditionals"],
        story=(
            "A bank website says a password is Strong only if it satisfies all of these:\n"
            "• at least 8 characters\n"
            "• at least one capital letter\n"
            "• at least one small letter\n"
            "• at least one digit\n"
            "• at least one special character (anything that is not a letter or digit)\n\n"
            "Otherwise it is Weak. Check the given password."
        ),
        input_format="A single line containing the password (no spaces).",
        output_format="Print Strong or Weak.",
        constraints=["1 ≤ length ≤ 100"],
        hints=["Use four boolean flags, one per character type.", "Scan once to set the flags, then check the length and all four flags together."],
        approach=(
            "Set flags while scanning: has_upper, has_lower, has_digit, has_special. Then combine them with the length rule using AND.\n\n"
            "This is a real-world validation you will write again and again in web development."
        ),
        time="O(length)", space="O(1)",
        solution='''
p = input().strip()
has_upper = has_lower = has_digit = has_special = False
for ch in p:
    if "A" <= ch <= "Z":
        has_upper = True
    elif "a" <= ch <= "z":
        has_lower = True
    elif "0" <= ch <= "9":
        has_digit = True
    else:
        has_special = True
if len(p) >= 8 and has_upper and has_lower and has_digit and has_special:
    print("Strong")
else:
    print("Weak")
''',
        samples=[
            ("Basha@2024", "10 characters with a capital, small letters, digits and a special character."),
            ("password", "No capital, digit or special character."),
            ("Ab1@", "Has every type but is only 4 characters long."),
            ("Coder123", "No special character."),
        ],
        edge=["A1b@cdef", "A1b@cde", "ABCDEFG1@", "abcdefg1@", "Abcdefgh@", "Abcdefg12", "_Chennai600001"],
        gen=_password,
    ),
    Spec(
        slug="valid-brackets",
        title="Valid Brackets",
        difficulty="medium",
        tags=["Strings", "Stack"],
        story=(
            "A code editor highlights mismatched brackets. A bracket string is valid if:\n"
            "• every opening bracket ( [ { is closed by the same type of bracket\n"
            "• brackets close in the correct order\n\n"
            "Check whether the given string of brackets is valid."
        ),
        input_format="A single string made of the characters ( ) [ ] { }.",
        output_format="Print Valid or Invalid.",
        constraints=["1 ≤ length ≤ 10^4"],
        hints=[
            "Use a stack. Push opening brackets.",
            "For a closing bracket, the top of the stack must be its matching opening bracket. Pop it. At the end, the stack must be empty.",
        ],
        approach=(
            "The most recently opened bracket must be closed first, which is exactly Last In, First Out, the behaviour of a stack.\n\n"
            "Three ways to fail: a closing bracket with an empty stack, a mismatched type, or leftover openings at the end. "
            "This is LeetCode #20 and your first stack problem."
        ),
        time="O(n)", space="O(n)",
        solution='''
s = input().strip()
pairs = {")": "(", "]": "[", "}": "{"}
stack = []
ok = True
for ch in s:
    if ch in "([{":
        stack.append(ch)
    else:
        if not stack or stack[-1] != pairs[ch]:
            ok = False
            break
        stack.pop()
if stack:
    ok = False
print("Valid" if ok else "Invalid")
''',
        samples=[
            ("()[]{}", "Each pair opens and closes properly."),
            ("([{}])", "Nested correctly, inside-out."),
            ("(]", "( is closed by ], which is the wrong type."),
            ("((", "Two brackets are never closed."),
        ],
        edge=["(", ")", "([)]", "{[]}", "){", "(((())))", "[{()}](){}"],
        gen=_brackets,
    ),
    Spec(
        slug="longest-common-prefix",
        title="Longest Common Prefix",
        difficulty="easy",
        tags=["Strings"],
        story=(
            "A phone's autocomplete suggests the longest beginning shared by all the words you've typed before.\n\n"
            "Given n words, find their longest common prefix. If they share no common beginning, print None."
        ),
        input_format="The first line has n.\nEach of the next n lines has one lowercase word.",
        output_format="Print the longest common prefix, or None.",
        constraints=["1 ≤ n ≤ 200", "1 ≤ word length ≤ 200"],
        hints=[
            "Take the first word as the candidate prefix.",
            "For every other word, shorten the candidate until the word starts with it.",
        ],
        approach=(
            "Start with the whole first word and trim it against each next word. "
            "The prefix can only get shorter, so once it becomes empty you can stop.\n\n"
            "Another way is to compare character by character, column-wise across all words. This is LeetCode #14."
        ),
        time="O(total characters)", space="O(length of first word)",
        solution='''
n = int(input())
words = [input().strip() for _ in range(n)]
prefix = words[0]
for w in words[1:]:
    while not w.startswith(prefix):
        prefix = prefix[:-1]
    if prefix == "":
        break
print(prefix if prefix else "None")
''',
        samples=[
            ("3\nflower\nflow\nflight", "All three start with fl."),
            ("3\ndog\nracecar\ncar", "No common first letter."),
            ("1\nbashabyte", "With one word, the whole word is the prefix."),
        ],
        edge=["2\na\na", "2\na\nb", "3\ninter\ninternet\ninterview", "2\nabc\nab"],
        gen=_prefix_case,
    ),
]
