"""Stage 1 (1-12): input, output and arithmetic.  Stage 2 (13-24): conditions."""

from .base import NAMES, Spec, line

SPECS = [
    # ───────────────────────── Stage 1: Input / Output / Arithmetic ─────────────────────────
    Spec(
        slug="namaste-coder",
        title="Namaste, Coder!",
        difficulty="easy",
        tags=["Basics", "Input/Output"],
        story=(
            "Every coding journey starts with a simple hello. BashaByte wants to welcome every new learner by name.\n\n"
            "Read the learner's name and print a welcome message in this exact format:\n"
            "Namaste, <name>! Welcome to BashaByte."
        ),
        input_format="A single line containing the name (one word).",
        output_format="Print the welcome message exactly as shown. Watch the comma, the exclamation mark and the full stop.",
        constraints=["1 ≤ length of name ≤ 30", "The name contains only English letters."],
        hints=[
            "First read the input into a variable, then print it inside the sentence.",
            "In Python you can use an f-string: print(f\"Namaste, {name}! Welcome to BashaByte.\")",
        ],
        approach=(
            "This problem is only about reading input and printing output in the exact format.\n\n"
            "Read the name, then print the fixed sentence with the name placed in the middle. "
            "Most wrong answers here come from a missing comma or a missing full stop, so copy the format carefully."
        ),
        time="O(1)", space="O(1)",
        solution='''
name = input().strip()
print(f"Namaste, {name}! Welcome to BashaByte.")
''',
        samples=[
            ("Ravi", "The name Ravi is placed inside the welcome sentence."),
            ("Priya", "Same sentence, only the name changes."),
            ("A", "Even a one-letter name gets the full welcome."),
        ],
        edge=["Subrahmanyam", "Venkatanarasimharajuvaripeta", "Zoya"],
        gen=lambda r: r.choice(NAMES) + r.choice(["", "", "a", "kumar", "devi"]),
    ),
    Spec(
        slug="chai-and-samosa-bill",
        title="Chai and Samosa Bill",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "At Raju's tea stall near the college gate, one cup of chai costs 12 rupees and one samosa costs 15 rupees.\n\n"
            "Your friends ordered c cups of chai and s samosas. Help Raju calculate the total bill."
        ),
        input_format="A single line with two integers c and s separated by a space.",
        output_format="Print the total bill in rupees.",
        constraints=["0 ≤ c ≤ 1000", "0 ≤ s ≤ 1000"],
        hints=[
            "Both numbers are on the same line, so split the line and convert each part to an integer.",
            "Total = c × 12 + s × 15",
        ],
        approach=(
            "Read the two numbers from one line. Multiply the chai count by 12 and the samosa count by 15, then add both.\n\n"
            "The key new skill here is reading two values from a single line."
        ),
        time="O(1)", space="O(1)",
        solution='''
c, s = map(int, input().split())
print(c * 12 + s * 15)
''',
        samples=[
            ("2 3", "2 chai = 24 rupees, 3 samosas = 45 rupees, total = 69."),
            ("5 0", "Only chai: 5 × 12 = 60."),
            ("0 4", "Only samosas: 4 × 15 = 60."),
        ],
        edge=["0 0", "1 1", "1000 1000", "1000 0", "0 1000"],
        gen=lambda r: line(r.randint(0, 1000), r.randint(0, 1000)),
    ),
    Spec(
        slug="cricket-ground-fencing",
        title="Cricket Ground Fencing",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "The village panchayat wants to prepare a rectangular cricket ground. They need two things:\n"
            "1. The area, to know how much grass to plant.\n"
            "2. The perimeter, to know how much fencing wire to buy.\n\n"
            "Given the length L and breadth B in metres, print both."
        ),
        input_format="A single line with two integers L and B.",
        output_format="Print the area on the first line and the perimeter on the second line.",
        constraints=["1 ≤ L, B ≤ 10000"],
        hints=["Area = L × B", "Perimeter = 2 × (L + B)"],
        approach=(
            "Apply the two school formulas directly: area is length times breadth, and perimeter is twice the sum of length and breadth.\n\n"
            "Print them on separate lines, area first."
        ),
        time="O(1)", space="O(1)",
        solution='''
L, B = map(int, input().split())
print(L * B)
print(2 * (L + B))
''',
        samples=[
            ("10 5", "Area = 10 × 5 = 50. Perimeter = 2 × (10 + 5) = 30."),
            ("7 7", "A square ground: area 49, perimeter 28."),
            ("100 60", "Area = 6000, perimeter = 320."),
        ],
        edge=["1 1", "10000 10000", "1 10000", "9999 2"],
        gen=lambda r: line(r.randint(1, 10000), r.randint(1, 10000)),
    ),
    Spec(
        slug="movie-duration",
        title="Movie Duration",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Booking apps show movie length like 2h 49m instead of 169 minutes, because it is easier to read.\n\n"
            "Given the total length of a movie in minutes, convert it into hours and minutes."
        ),
        input_format="A single integer M, the length in minutes.",
        output_format="Print in the format <hours>h <minutes>m, for example 2h 49m.",
        constraints=["0 ≤ M ≤ 10000"],
        hints=[
            "Hours = M divided by 60, keeping only the whole part (integer division).",
            "Remaining minutes = M % 60 (the remainder).",
        ],
        approach=(
            "This problem introduces the two most useful operators in programming: integer division and remainder.\n\n"
            "M // 60 tells you how many full hours fit, and M % 60 gives the minutes left over."
        ),
        time="O(1)", space="O(1)",
        solution='''
M = int(input())
print(f"{M // 60}h {M % 60}m")
''',
        samples=[
            ("169", "169 = 2 × 60 + 49, so 2 hours and 49 minutes."),
            ("60", "Exactly one hour, zero minutes."),
            ("45", "Less than an hour, so 0 hours and 45 minutes."),
        ],
        edge=["0", "59", "61", "120", "10000", "1"],
        gen=lambda r: str(r.randint(0, 10000)),
    ),
    Spec(
        slug="celsius-to-fahrenheit",
        title="Weather Report: Celsius to Fahrenheit",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Your cousin in the USA keeps asking about the weather in Chennai, but they only understand Fahrenheit.\n\n"
            "Convert the temperature C (in Celsius) to Fahrenheit using F = C × 9 / 5 + 32."
        ),
        input_format="A single integer C.",
        output_format="Print F rounded to exactly 2 decimal places.",
        constraints=["-100 ≤ C ≤ 100"],
        hints=[
            "Be careful with integer division. In C, C++ and Java, 9 / 5 is 1, not 1.8. Use 9.0 / 5.",
            "Print with 2 decimals, for example f\"{F:.2f}\" in Python or printf(\"%.2f\") in C.",
        ],
        approach=(
            "Use the formula with decimal (floating point) arithmetic, then format the answer to two decimal places.\n\n"
            "This problem teaches the difference between integer division and decimal division, a very common beginner bug."
        ),
        time="O(1)", space="O(1)",
        solution='''
C = int(input())
F = C * 9 / 5 + 32
print(f"{F:.2f}")
''',
        samples=[
            ("37", "37 × 9 / 5 + 32 = 98.60, normal body temperature."),
            ("0", "Water freezes at 0 °C, which is 32.00 °F."),
            ("-40", "-40 is the special point where both scales are equal."),
        ],
        edge=["100", "-100", "1", "-1", "45", "-17"],
        gen=lambda r: str(r.randint(-100, 100)),
    ),
    Spec(
        slug="simple-interest-calculator",
        title="Simple Interest Calculator",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Meena aunty kept some money in a post office deposit. She wants to know how much interest she will earn.\n\n"
            "Given principal P (rupees), rate R (percent per year) and time T (years), find the simple interest using SI = P × R × T / 100."
        ),
        input_format="A single line with three integers P, R and T.",
        output_format="Print the simple interest rounded to exactly 2 decimal places.",
        constraints=["1 ≤ P ≤ 1000000", "1 ≤ R ≤ 50", "1 ≤ T ≤ 30"],
        hints=[
            "Read three integers from the same line.",
            "Divide by 100.0 (decimal), not 100, so that you don't lose the paise.",
        ],
        approach=(
            "Read the three values, apply the formula with decimal division, and print with two decimal places.\n\n"
            "P × R × T can reach 1.5 × 10^9, which still fits in a normal int, but using a double for the division keeps the paise."
        ),
        time="O(1)", space="O(1)",
        solution='''
P, R, T = map(int, input().split())
si = P * R * T / 100
print(f"{si:.2f}")
''',
        samples=[
            ("10000 5 2", "10000 × 5 × 2 / 100 = 1000.00"),
            ("1500 7 3", "1500 × 7 × 3 / 100 = 315.00"),
            ("999 3 1", "999 × 3 × 1 / 100 = 29.97, so the paise matter here."),
        ],
        edge=["1 1 1", "1000000 50 30", "12345 7 3", "7 1 1"],
        gen=lambda r: line(r.randint(1, 1000000), r.randint(1, 50), r.randint(1, 30)),
    ),
    Spec(
        slug="swap-two-numbers",
        title="Swap the Seats",
        difficulty="easy",
        tags=["Basics", "Variables"],
        story=(
            "In class, Rohan is sitting on bench a and Kabir on bench b. The teacher asks them to exchange benches.\n\n"
            "Read two numbers a and b, swap their values, and print the new values in the format shown."
        ),
        input_format="A single line with two integers a and b.",
        output_format="Print two lines:\na = <new value of a>\nb = <new value of b>",
        constraints=["-10^9 ≤ a, b ≤ 10^9"],
        hints=[
            "If you write a = b first, the old value of a is lost. Keep a copy in a temporary variable.",
            "temp = a; a = b; b = temp. Python also allows a, b = b, a.",
        ],
        approach=(
            "Swapping is a basic building block used later in sorting and array problems.\n\n"
            "Use a temporary variable to hold one value while you overwrite it, then print in the required format."
        ),
        time="O(1)", space="O(1)",
        solution='''
a, b = map(int, input().split())
temp = a
a = b
b = temp
print(f"a = {a}")
print(f"b = {b}")
''',
        samples=[
            ("3 7", "After swapping, a gets 7 and b gets 3."),
            ("10 10", "Both are equal, so nothing visibly changes."),
            ("-5 8", "Negative numbers swap the same way."),
        ],
        edge=["0 0", "1000000000 -1000000000", "-1 -2", "0 5"],
        gen=lambda r: line(r.randint(-10**9, 10**9), r.randint(-10**9, 10**9)),
    ),
    Spec(
        slug="last-digit-and-rest",
        title="Last Digit of the Bus Number",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Bus conductors in Bengaluru often shout only the last digit of a bus number. Let's teach the computer to split a number.\n\n"
            "Given a number n, print its last digit, and then the number that remains after removing that last digit."
        ),
        input_format="A single integer n.",
        output_format="Print the last digit on the first line and the remaining number on the second line.",
        constraints=["0 ≤ n ≤ 10^9"],
        hints=["n % 10 gives the last digit.", "n // 10 removes the last digit (integer division)."],
        approach=(
            "% 10 and // 10 are the two tools you will use in almost every digit problem: counting digits, reversing, and checking palindromes.\n\n"
            "Practise them here on a single step."
        ),
        time="O(1)", space="O(1)",
        solution='''
n = int(input())
print(n % 10)
print(n // 10)
''',
        samples=[
            ("1234", "Last digit is 4. Removing it leaves 123."),
            ("500", "Last digit is 0. Remaining number is 50."),
            ("7", "Last digit is 7. Nothing is left, so the remaining number is 0."),
        ],
        edge=["0", "10", "1000000000", "99", "101"],
        gen=lambda r: str(r.randint(0, 10**r.randint(1, 9))),
    ),
    Spec(
        slug="sharing-laddoos",
        title="Sharing Laddoos",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Grandma made n laddoos for Diwali and wants to share them equally among k grandchildren. "
            "Every child must get the same number of laddoos, and the extra ones go back into the dabba.\n\n"
            "Find how many laddoos each child gets and how many are left in the dabba."
        ),
        input_format="A single line with two integers n and k.",
        output_format="Print the laddoos per child on the first line and the leftover laddoos on the second line.",
        constraints=["0 ≤ n ≤ 10^9", "1 ≤ k ≤ 10^6"],
        hints=["Each child gets n // k.", "The leftover is n % k."],
        approach=(
            "Equal sharing is integer division, and the leftover is the remainder.\n\n"
            "This is the same idea as the movie duration problem, now with a divisor that changes."
        ),
        time="O(1)", space="O(1)",
        solution='''
n, k = map(int, input().split())
print(n // k)
print(n % k)
''',
        samples=[
            ("17 5", "5 × 3 = 15, so each child gets 3 and 2 are left."),
            ("20 4", "Shared perfectly: 5 each, 0 left."),
            ("3 7", "Fewer laddoos than children: everyone gets 0 and all 3 stay in the dabba."),
        ],
        edge=["0 1", "1 1", "1000000000 1", "1000000000 1000000", "999999 1000000"],
        gen=lambda r: line(r.randint(0, 10**9), r.randint(1, 10**6)),
    ),
    Spec(
        slug="average-of-three-marks",
        title="Average of Three Marks",
        difficulty="easy",
        tags=["Basics", "Math"],
        story=(
            "Anjali wrote three unit tests in Maths. Her class teacher wants the average mark for the report card.\n\n"
            "Given the three marks, print their average."
        ),
        input_format="A single line with three integers a, b and c.",
        output_format="Print the average rounded to exactly 2 decimal places.",
        constraints=["0 ≤ a, b, c ≤ 100"],
        hints=["Average = (a + b + c) / 3", "Divide by 3.0 to get decimals, then print with 2 decimal places."],
        approach=(
            "Add the three marks and divide by three using decimal division. Format the output to two decimal places.\n\n"
            "Notice that the sum divided by 3 can give answers like 66.67, so integer division would be wrong."
        ),
        time="O(1)", space="O(1)",
        solution='''
a, b, c = map(int, input().split())
avg = (a + b + c) / 3
print(f"{avg:.2f}")
''',
        samples=[
            ("90 80 70", "(90 + 80 + 70) / 3 = 80.00"),
            ("100 100 99", "299 / 3 = 99.666..., which rounds to 99.67."),
            ("0 0 1", "1 / 3 = 0.333..., which rounds to 0.33."),
        ],
        edge=["0 0 0", "100 100 100", "35 36 37", "50 51 51"],
        gen=lambda r: line(r.randint(0, 100), r.randint(0, 100), r.randint(0, 100)),
    ),
    Spec(
        slug="train-journey-timer",
        title="Train Journey Timer",
        difficulty="easy",
        tags=["Basics", "Math", "Formatting"],
        story=(
            "The railway display board shows journey time as HH:MM:SS. The system only stores the total number of seconds.\n\n"
            "Given S seconds, convert it into hours, minutes and seconds, each shown with two digits."
        ),
        input_format="A single integer S.",
        output_format="Print the time as HH:MM:SS with leading zeros, for example 01:05:09.",
        constraints=["0 ≤ S < 86400 (less than one day)"],
        hints=[
            "hours = S // 3600, minutes = (S % 3600) // 60, seconds = S % 60.",
            "To always print two digits, use f\"{x:02d}\" in Python or printf(\"%02d\") in C.",
        ],
        approach=(
            "First take out the full hours, then the full minutes from what remains, and whatever is left is seconds.\n\n"
            "The new skill is zero-padding: 5 must print as 05."
        ),
        time="O(1)", space="O(1)",
        solution='''
S = int(input())
h = S // 3600
m = (S % 3600) // 60
s = S % 60
print(f"{h:02d}:{m:02d}:{s:02d}")
''',
        samples=[
            ("3909", "3909 = 1 hour (3600) + 5 minutes (300) + 9 seconds, so 01:05:09."),
            ("59", "Less than a minute: 00:00:59."),
            ("86399", "The last second of the day: 23:59:59."),
        ],
        edge=["0", "60", "3600", "43200", "7322", "36000"],
        gen=lambda r: str(r.randint(0, 86399)),
    ),
    Spec(
        slug="atm-note-counter",
        title="ATM Note Counter",
        difficulty="easy",
        tags=["Basics", "Math", "Greedy"],
        story=(
            "An ATM has only 500, 200 and 100 rupee notes. It always gives the fewest notes possible by using the biggest notes first.\n\n"
            "Given the amount to withdraw, print how many notes of each type the ATM gives."
        ),
        input_format="A single integer A, the amount (always a multiple of 100).",
        output_format="Print three lines in this exact format:\n500: <count>\n200: <count>\n100: <count>",
        constraints=["100 ≤ A ≤ 100000", "A is a multiple of 100"],
        hints=[
            "Number of 500 notes = A // 500. Then reduce A to A % 500.",
            "Repeat the same step with 200, and whatever is left is paid in 100 notes.",
        ],
        approach=(
            "Take as many of the biggest note as possible, then move to the next note with the remaining amount. "
            "This 'biggest first' idea is called a greedy approach.\n\n"
            "For 500, 200 and 100 it always gives the fewest notes."
        ),
        time="O(1)", space="O(1)",
        solution='''
A = int(input())
n500 = A // 500
A = A % 500
n200 = A // 200
A = A % 200
n100 = A // 100
print(f"500: {n500}")
print(f"200: {n200}")
print(f"100: {n100}")
''',
        samples=[
            ("1800", "3 × 500 = 1500, then 300 is left: 1 × 200 + 1 × 100."),
            ("400", "No 500 note fits, so 2 × 200."),
            ("100", "Just one 100 rupee note."),
        ],
        edge=["500", "900", "100000", "300", "700", "99900"],
        gen=lambda r: str(r.randint(1, 1000) * 100),
    ),

    # ───────────────────────── Stage 2: Conditions ─────────────────────────
    Spec(
        slug="bank-balance-status",
        title="Bank Balance Status",
        difficulty="easy",
        tags=["Conditionals"],
        story=(
            "Your UPI app checks your balance before every payment. If the balance is above zero it is Positive, "
            "below zero (overdraft) it is Negative, and exactly zero is Zero.\n\n"
            "Given the balance, print its status."
        ),
        input_format="A single integer n, the balance.",
        output_format="Print Positive, Negative or Zero.",
        constraints=["-10^9 ≤ n ≤ 10^9"],
        hints=["You need three branches: if, else if (elif) and else.", "Check n > 0, then n < 0, otherwise it is zero."],
        approach=(
            "This is your first if, elif, else problem. There are exactly three possibilities, and each one gets its own branch.\n\n"
            "Always make sure every possible input lands in exactly one branch."
        ),
        time="O(1)", space="O(1)",
        solution='''
n = int(input())
if n > 0:
    print("Positive")
elif n < 0:
    print("Negative")
else:
    print("Zero")
''',
        samples=[
            ("2500", "2500 is greater than 0."),
            ("-300", "-300 is less than 0, an overdraft."),
            ("0", "Exactly zero."),
        ],
        edge=["1", "-1", "1000000000", "-1000000000"],
        gen=lambda r: str(r.choice([r.randint(-10**9, 10**9), r.randint(-50, 50)])),
    ),
    Spec(
        slug="tallest-of-three-friends",
        title="Tallest of Three Friends",
        difficulty="easy",
        tags=["Conditionals"],
        story=(
            "Aarav, Kabir and Meera are standing for the class photo. The tallest one has to stand in the middle.\n\n"
            "Given their three heights in centimetres, print the greatest height."
        ),
        input_format="A single line with three integers a, b and c.",
        output_format="Print the greatest of the three numbers.",
        constraints=["1 ≤ a, b, c ≤ 300", "Heights may be equal."],
        hints=[
            "Compare a with b and c first. If a is greater than or equal to both, a is the answer.",
            "Use >= so that equal heights are handled correctly.",
        ],
        approach=(
            "Check each person in turn: if a ≥ b and a ≥ c, answer a; else if b ≥ c, answer b; otherwise answer c.\n\n"
            "Try doing it with if-else first, even though most languages have a built-in max function."
        ),
        time="O(1)", space="O(1)",
        solution='''
a, b, c = map(int, input().split())
if a >= b and a >= c:
    print(a)
elif b >= c:
    print(b)
else:
    print(c)
''',
        samples=[
            ("150 162 158", "162 is the greatest of the three."),
            ("170 170 165", "Two friends share the greatest height of 170."),
            ("120 110 175", "The third friend is the tallest."),
        ],
        edge=["1 1 1", "300 1 1", "1 300 1", "1 1 300", "200 200 200", "5 4 5"],
        gen=lambda r: line(r.randint(100, 200), r.randint(100, 200), r.randint(100, 200)),
    ),
    Spec(
        slug="exam-grade-calculator",
        title="Exam Grade Calculator",
        difficulty="easy",
        tags=["Conditionals"],
        story=(
            "The school converts marks into grades for the report card:\n"
            "90 to 100 → A\n"
            "75 to 89 → B\n"
            "60 to 74 → C\n"
            "40 to 59 → D\n"
            "Below 40 → F\n\n"
            "Given a student's marks, print the grade."
        ),
        input_format="A single integer m, the marks.",
        output_format="Print one letter: A, B, C, D or F.",
        constraints=["0 ≤ m ≤ 100"],
        hints=[
            "Start checking from the top grade: if m >= 90, then elif m >= 75, and so on.",
            "Checking in this order means you never need a 'between' condition.",
        ],
        approach=(
            "A ladder of if, elif checks from the highest grade to the lowest. "
            "Because each check runs only when the previous ones failed, m >= 75 automatically means 75 to 89.\n\n"
            "Always test the boundary marks, like 89, 90, 39 and 40."
        ),
        time="O(1)", space="O(1)",
        solution='''
m = int(input())
if m >= 90:
    print("A")
elif m >= 75:
    print("B")
elif m >= 60:
    print("C")
elif m >= 40:
    print("D")
else:
    print("F")
''',
        samples=[
            ("95", "95 is between 90 and 100, so grade A."),
            ("75", "75 is exactly the start of grade B."),
            ("39", "39 is just below 40, so grade F."),
            ("60", "60 is the lowest mark for grade C."),
        ],
        edge=["0", "100", "90", "89", "74", "59", "40", "41"],
        gen=lambda r: str(r.randint(0, 100)),
    ),
    Spec(
        slug="triangle-type",
        title="Triangle Type Checker",
        difficulty="easy",
        tags=["Conditionals", "Math"],
        story=(
            "A carpenter has three wooden sticks. Can he make a triangle with them? And if yes, what kind?\n\n"
            "Three sides make a valid triangle only if the sum of any two sides is greater than the third side.\n"
            "• All three sides equal → Equilateral\n"
            "• Exactly two sides equal → Isosceles\n"
            "• All sides different → Scalene"
        ),
        input_format="A single line with three integers a, b and c.",
        output_format="Print Invalid, Equilateral, Isosceles or Scalene.",
        constraints=["1 ≤ a, b, c ≤ 1000"],
        hints=[
            "Check validity first: a + b > c and a + c > b and b + c > a.",
            "Only if it is valid, check how many sides are equal.",
        ],
        approach=(
            "First rule out invalid triangles, because a stick set like 1, 2, 10 cannot close. "
            "Then compare the sides: all equal, any two equal, or none equal.\n\n"
            "The order of checks matters: Equilateral must be checked before Isosceles."
        ),
        time="O(1)", space="O(1)",
        solution='''
a, b, c = map(int, input().split())
if a + b <= c or a + c <= b or b + c <= a:
    print("Invalid")
elif a == b == c:
    print("Equilateral")
elif a == b or b == c or a == c:
    print("Isosceles")
else:
    print("Scalene")
''',
        samples=[
            ("5 5 5", "All three sides are equal."),
            ("5 5 8", "Two sides are equal and 5 + 5 > 8."),
            ("3 4 5", "All sides are different and form a valid triangle."),
            ("1 2 3", "1 + 2 = 3, which is not greater than 3, so the sticks lie flat."),
        ],
        edge=["1 1 1", "1 1 2", "10 1 1", "1000 1000 1", "2 3 4", "7 10 7", "1 10 12", "500 400 300"],
        gen=lambda r: line(r.randint(1, 20), r.randint(1, 20), r.randint(1, 20)),
    ),
    Spec(
        slug="vowel-or-consonant",
        title="Vowel or Consonant",
        difficulty="easy",
        tags=["Conditionals", "Strings"],
        story=(
            "In the Antakshari-style letter game, vowels score double points. "
            "Given one English letter (capital or small), tell whether it is a vowel or a consonant.\n\n"
            "Vowels are a, e, i, o, u (in either case)."
        ),
        input_format="A single English letter.",
        output_format="Print Vowel or Consonant.",
        constraints=["The input is one letter from a-z or A-Z."],
        hints=[
            "Convert the letter to lowercase first so you only check five cases.",
            "In Python: if ch in \"aeiou\".",
        ],
        approach=(
            "Normalise the case and check membership in the vowel set.\n\n"
            "Lowercasing first is a common trick to avoid writing ten conditions."
        ),
        time="O(1)", space="O(1)",
        solution='''
ch = input().strip().lower()
if ch in "aeiou":
    print("Vowel")
else:
    print("Consonant")
''',
        samples=[
            ("a", "a is a vowel."),
            ("K", "K is a consonant. Capital letters count too."),
            ("E", "E is a vowel in capital form."),
        ],
        edge=["i", "o", "u", "U", "z", "Z", "y", "b", "I", "O"],
        gen=lambda r: r.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ),
    Spec(
        slug="movie-ticket-price",
        title="Movie Ticket Price",
        difficulty="easy",
        tags=["Conditionals"],
        story=(
            "A single-screen theatre in Madurai prices tickets by age:\n"
            "• Below 3 years → free (0 rupees)\n"
            "• 3 to 12 years → 100 rupees\n"
            "• 13 to 59 years → 200 rupees\n"
            "• 60 years and above → 120 rupees (senior citizen discount)\n\n"
            "Given a person's age, print the ticket price."
        ),
        input_format="A single integer age.",
        output_format="Print the ticket price.",
        constraints=["0 ≤ age ≤ 120"],
        hints=["Check the ranges in increasing order of age.", "Test the boundaries carefully: 2, 3, 12, 13, 59 and 60."],
        approach=(
            "This is another if-else ladder, this time with ranges that don't increase in price, so you cannot just compare 'price >= something'.\n\n"
            "Check age < 3, age <= 12, age <= 59, and otherwise it is a senior."
        ),
        time="O(1)", space="O(1)",
        solution='''
age = int(input())
if age < 3:
    print(0)
elif age <= 12:
    print(100)
elif age <= 59:
    print(200)
else:
    print(120)
''',
        samples=[
            ("8", "8 is between 3 and 12, so 100 rupees."),
            ("65", "Senior citizen, so 120 rupees."),
            ("2", "Babies below 3 watch free."),
            ("13", "13 has just crossed the child range, so 200 rupees."),
        ],
        edge=["0", "3", "12", "59", "60", "120", "30"],
        gen=lambda r: str(r.randint(0, 120)),
    ),
    Spec(
        slug="clap-game-fizzbuzz",
        title="Clap Game (FizzBuzz)",
        difficulty="easy",
        tags=["Conditionals", "Math"],
        story=(
            "In the class clap game, students count numbers, but:\n"
            "• If the number is divisible by both 3 and 5, say FizzBuzz\n"
            "• If it is divisible only by 3, say Fizz\n"
            "• If it is divisible only by 5, say Buzz\n"
            "• Otherwise, just say the number\n\n"
            "Given a number n, print what the student should say."
        ),
        input_format="A single integer n.",
        output_format="Print FizzBuzz, Fizz, Buzz or the number itself.",
        constraints=["1 ≤ n ≤ 10^6"],
        hints=[
            "Check divisibility by both 3 and 5 (that is, by 15) first. Why must this come first?",
            "n % 3 == 0 means n is divisible by 3.",
        ],
        approach=(
            "The trick is the order of checks. If you test 'divisible by 3' first, 15 would wrongly print Fizz.\n\n"
            "Always check the most specific condition first."
        ),
        time="O(1)", space="O(1)",
        solution='''
n = int(input())
if n % 15 == 0:
    print("FizzBuzz")
elif n % 3 == 0:
    print("Fizz")
elif n % 5 == 0:
    print("Buzz")
else:
    print(n)
''',
        samples=[
            ("15", "15 is divisible by both 3 and 5."),
            ("9", "9 is divisible by 3 only."),
            ("10", "10 is divisible by 5 only."),
            ("7", "7 is not divisible by 3 or 5, so we say 7."),
        ],
        edge=["1", "3", "5", "30", "1000000", "999999", "45", "98"],
        gen=lambda r: str(r.randint(1, 10**6)),
    ),
    Spec(
        slug="which-quadrant",
        title="Which Quadrant?",
        difficulty="easy",
        tags=["Conditionals", "Math"],
        story=(
            "A drone pilot reports the drone's position as a point (x, y) on a graph.\n\n"
            "Tell where the point lies:\n"
            "• Quadrant 1 (x > 0, y > 0), Quadrant 2 (x < 0, y > 0), Quadrant 3 (x < 0, y < 0), Quadrant 4 (x > 0, y < 0)\n"
            "• Origin if both are 0\n"
            "• X-axis if only y is 0, Y-axis if only x is 0"
        ),
        input_format="A single line with two integers x and y.",
        output_format="Print one of: Quadrant 1, Quadrant 2, Quadrant 3, Quadrant 4, Origin, X-axis, Y-axis.",
        constraints=["-1000 ≤ x, y ≤ 1000"],
        hints=[
            "Handle the zero cases first (Origin, then the axes).",
            "After that, x and y are both non-zero and you only need to check their signs.",
        ],
        approach=(
            "Seven possible answers sounds like a lot, but if you handle the special zero cases first, "
            "the remaining four quadrants are simple sign checks.\n\n"
            "Handling special cases first is a habit that will save you in many problems."
        ),
        time="O(1)", space="O(1)",
        solution='''
x, y = map(int, input().split())
if x == 0 and y == 0:
    print("Origin")
elif y == 0:
    print("X-axis")
elif x == 0:
    print("Y-axis")
elif x > 0 and y > 0:
    print("Quadrant 1")
elif x < 0 and y > 0:
    print("Quadrant 2")
elif x < 0:
    print("Quadrant 3")
else:
    print("Quadrant 4")
''',
        samples=[
            ("3 4", "Both positive, so Quadrant 1."),
            ("-2 5", "x negative and y positive, so Quadrant 2."),
            ("0 0", "The drone is at the centre."),
            ("7 0", "y is 0, so the point is on the X-axis."),
        ],
        edge=["0 9", "-3 -3", "5 -1", "-1000 0", "0 -1000", "1000 1000", "-1 1", "1 -1"],
        gen=lambda r: line(r.randint(-10, 10), r.randint(-10, 10)),
    ),
    Spec(
        slug="festival-sale-discount",
        title="Festival Sale Discount",
        difficulty="easy",
        tags=["Conditionals", "Math"],
        story=(
            "During the Diwali sale, a clothing shop gives:\n"
            "• 20% off if the bill is 5000 rupees or more\n"
            "• 10% off if the bill is 2000 rupees or more (but less than 5000)\n"
            "• No discount below 2000\n\n"
            "Given the bill amount, print the final amount to pay."
        ),
        input_format="A single integer B, the bill amount.",
        output_format="Print the amount to pay, rounded to exactly 2 decimal places.",
        constraints=["1 ≤ B ≤ 1000000"],
        hints=[
            "20% off means you pay 80%, that is B × 0.80.",
            "Check the bigger discount first.",
        ],
        approach=(
            "Pick the discount with an if-elif ladder (largest first), compute the payable amount, and format it to two decimals.\n\n"
            "Multiplying by 0.8 or 0.9 is the same as subtracting the discount."
        ),
        time="O(1)", space="O(1)",
        solution='''
B = int(input())
if B >= 5000:
    pay = B * 0.80
elif B >= 2000:
    pay = B * 0.90
else:
    pay = B
print(f"{pay:.2f}")
''',
        samples=[
            ("6000", "20% off: 6000 × 0.80 = 4800.00"),
            ("2500", "10% off: 2500 × 0.90 = 2250.00"),
            ("1999", "Below 2000, no discount."),
        ],
        edge=["2000", "5000", "4999", "1", "1000000", "2001", "5001"],
        gen=lambda r: str(r.randint(1, 20000)),
    ),
    Spec(
        slug="day-of-the-week",
        title="Day of the Week",
        difficulty="easy",
        tags=["Conditionals"],
        story=(
            "The school timetable app stores days as numbers: 1 is Monday, 2 is Tuesday, and so on up to 7, which is Sunday.\n\n"
            "Given a number, print the day's name. If the number is not between 1 and 7, print Invalid."
        ),
        input_format="A single integer d.",
        output_format="Print the day name (Monday, Tuesday, …, Sunday) or Invalid.",
        constraints=["-100 ≤ d ≤ 100"],
        hints=[
            "Check for invalid input first: d < 1 or d > 7.",
            "A list of day names can replace seven if-conditions: days[d - 1].",
        ],
        approach=(
            "You can write seven if-conditions, but a smarter way is to keep the names in a list and pick the (d - 1)th element.\n\n"
            "Validate the input before using it as an index. This idea, 'check before you access', prevents many crashes."
        ),
        time="O(1)", space="O(1)",
        solution='''
d = int(input())
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
if 1 <= d <= 7:
    print(days[d - 1])
else:
    print("Invalid")
''',
        samples=[
            ("1", "Day 1 is Monday."),
            ("7", "Day 7 is Sunday."),
            ("9", "There is no day 9."),
        ],
        edge=["2", "3", "4", "5", "6", "0", "-1", "8", "100", "-100"],
        gen=lambda r: str(r.randint(-10, 15)),
    ),
    Spec(
        slug="profit-or-loss",
        title="Profit or Loss",
        difficulty="easy",
        tags=["Conditionals", "Math"],
        story=(
            "Gopal buys vegetables wholesale and sells them in the local market.\n\n"
            "Given the cost price and the selling price, tell him whether he made a profit or a loss, and how much."
        ),
        input_format="A single line with two integers: cost price C and selling price S.",
        output_format="Print Profit <amount>, Loss <amount>, or No Profit No Loss.",
        constraints=["1 ≤ C, S ≤ 10^6"],
        hints=["If S > C, profit = S - C.", "If C > S, loss = C - S. Otherwise they are equal."],
        approach=(
            "Compare the two prices. The amount is always the positive difference, so subtract the smaller from the bigger.\n\n"
            "Print a word and a number together on one line, with exactly one space between them."
        ),
        time="O(1)", space="O(1)",
        solution='''
C, S = map(int, input().split())
if S > C:
    print(f"Profit {S - C}")
elif C > S:
    print(f"Loss {C - S}")
else:
    print("No Profit No Loss")
''',
        samples=[
            ("500 650", "Sold for more than cost: 650 - 500 = 150 profit."),
            ("800 720", "Sold for less: 800 - 720 = 80 loss."),
            ("300 300", "Same price, so neither profit nor loss."),
        ],
        edge=["1 1", "1 1000000", "1000000 1", "999 1000", "1000 999"],
        gen=lambda r: line(r.randint(1, 5000), r.randint(1, 5000)),
    ),
    Spec(
        slug="character-type",
        title="What Kind of Character?",
        difficulty="easy",
        tags=["Conditionals", "Strings"],
        story=(
            "When you create a password, websites check what kind of characters you typed.\n\n"
            "Given a single character, print:\n"
            "• Uppercase for A-Z\n"
            "• Lowercase for a-z\n"
            "• Digit for 0-9\n"
            "• Special for anything else"
        ),
        input_format="A single character (never a space).",
        output_format="Print Uppercase, Lowercase, Digit or Special.",
        constraints=["The character is a printable ASCII character other than space."],
        hints=[
            "Characters can be compared: 'A' <= ch <= 'Z' checks for an uppercase letter.",
            "Python also has ch.isupper(), ch.islower() and ch.isdigit().",
        ],
        approach=(
            "Characters are stored as numbers (ASCII codes), and A-Z, a-z and 0-9 are each continuous ranges. "
            "So a range comparison tells you the type.\n\n"
            "Anything that falls in none of the three ranges is Special."
        ),
        time="O(1)", space="O(1)",
        solution='''
ch = input()[0]
if "A" <= ch <= "Z":
    print("Uppercase")
elif "a" <= ch <= "z":
    print("Lowercase")
elif "0" <= ch <= "9":
    print("Digit")
else:
    print("Special")
''',
        samples=[
            ("G", "G is between A and Z."),
            ("m", "m is between a and z."),
            ("7", "7 is a digit."),
            ("@", "@ is not a letter or digit."),
        ],
        edge=["A", "Z", "a", "z", "0", "9", "#", "_", "[", "`", "{", "/", ":"],
        gen=lambda r: r.choice("ABCXYZabcxyz0123456789!@#$%^&*()-+=?"),
    ),
]
