"""Stage 3 (25-40): loops and number logic.  Stage 4 (41-48): patterns."""

from .base import Spec, line


def _pow_case(r):
    while True:
        a, b = r.randint(0, 10), r.randint(0, 18)
        if a ** b <= 10**18:
            return line(a, b)


def _binary(r):
    return bin(r.randint(1, 2**r.randint(1, 30) - 1))[2:]


SPECS = [
    # ───────────────────────── Stage 3: Loops ─────────────────────────
    Spec(
        slug="rocket-countdown",
        title="Rocket Launch Countdown",
        difficulty="easy",
        tags=["Loops"],
        story=(
            "ISRO's mission control counts down before every launch. "
            "Given a starting number n, print the countdown from n down to 1, one number per line, and then print Liftoff!"
        ),
        input_format="A single integer n.",
        output_format="Print n, n-1, …, 1 on separate lines, then Liftoff! on the last line.",
        constraints=["1 ≤ n ≤ 100"],
        hints=[
            "A loop can count backwards: for i in range(n, 0, -1).",
            "Print Liftoff! after the loop ends, not inside it.",
        ],
        approach=(
            "Your first loop. Start the counter at n, print it, reduce it by one, and stop after printing 1.\n\n"
            "The final message goes outside the loop so it prints exactly once."
        ),
        time="O(n)", space="O(1)",
        solution='''
n = int(input())
for i in range(n, 0, -1):
    print(i)
print("Liftoff!")
''',
        samples=[
            ("5", "Count 5, 4, 3, 2, 1 and then launch."),
            ("1", "Only one number before the launch."),
            ("3", "3, 2, 1, Liftoff!"),
        ],
        edge=["2", "10", "100", "50"],
        gen=lambda r: str(r.randint(1, 100)),
    ),
    Spec(
        slug="even-numbers-till-n",
        title="Even Numbers Till N",
        difficulty="easy",
        tags=["Loops"],
        story=(
            "The PT teacher asks students standing at even positions to step forward. "
            "Given N, print all even numbers from 2 to N in one line."
        ),
        input_format="A single integer N.",
        output_format="Print the even numbers from 2 to N separated by single spaces.",
        constraints=["2 ≤ N ≤ 1000"],
        hints=[
            "Start at 2 and jump by 2 each time: range(2, N + 1, 2).",
            "Collect the numbers and print them with spaces between, with no extra space at the end.",
        ],
        approach=(
            "Either loop over all numbers and keep the ones with i % 2 == 0, or start at 2 and step by 2. The second way does half the work.\n\n"
            "This is the first problem where the output is a list of numbers on one line, so learn to join them with single spaces."
        ),
        time="O(N)", space="O(N)",
        solution='''
N = int(input())
evens = []
for i in range(2, N + 1, 2):
    evens.append(str(i))
print(" ".join(evens))
''',
        samples=[
            ("10", "Even numbers up to 10 are 2, 4, 6, 8 and 10."),
            ("7", "7 is odd, so the list stops at 6."),
            ("2", "Only one even number: 2."),
        ],
        edge=["3", "4", "1000", "999", "21"],
        gen=lambda r: str(r.randint(2, 200)),
    ),
    Spec(
        slug="factorial-of-n",
        title="Factorial of N",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "In how many ways can N students stand in a line for the school assembly? The answer is N factorial (N!).\n\n"
            "N! = 1 × 2 × 3 × … × N, and by definition 0! = 1."
        ),
        input_format="A single integer N.",
        output_format="Print N!.",
        constraints=[
            "0 ≤ N ≤ 20",
            "20! is about 2.4 × 10^18. Use long long in C/C++ or long in Java.",
        ],
        hints=[
            "Start with result = 1 (not 0!) and multiply it by every number from 1 to N.",
            "For N = 0 the loop does not run at all, and result stays 1, which is correct.",
        ],
        approach=(
            "This is the 'accumulator' pattern with multiplication. The starting value must be 1, because multiplying anything by 0 gives 0.\n\n"
            "Factorials grow very fast, which is why the limit is only 20."
        ),
        time="O(N)", space="O(1)",
        solution='''
N = int(input())
result = 1
for i in range(1, N + 1):
    result = result * i
print(result)
''',
        samples=[
            ("5", "5! = 1 × 2 × 3 × 4 × 5 = 120"),
            ("0", "0! is defined as 1."),
            ("10", "10! = 3628800"),
        ],
        edge=["1", "2", "3", "20", "19", "12", "13"],
        gen=lambda r: str(r.randint(0, 20)),
    ),
    Spec(
        slug="count-the-digits",
        title="Count the Digits",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "A mobile number has 10 digits and a PIN code has 6. "
            "Given any non-negative number n, count how many digits it has, using maths, not string length."
        ),
        input_format="A single integer n.",
        output_format="Print the number of digits in n.",
        constraints=["0 ≤ n ≤ 10^18"],
        hints=[
            "Keep removing the last digit with n // 10 and count how many times you can do it.",
            "Careful: 0 has 1 digit, but a 'while n > 0' loop would count 0 digits.",
        ],
        approach=(
            "Repeatedly chop off the last digit until nothing is left, counting each chop. This is the while-loop version of the % and // tricks.\n\n"
            "The number 0 is the classic trap. Handle it separately."
        ),
        time="O(number of digits)", space="O(1)",
        solution='''
n = int(input())
if n == 0:
    print(1)
else:
    count = 0
    while n > 0:
        n = n // 10
        count += 1
    print(count)
''',
        samples=[
            ("9876543210", "A 10-digit number, like a mobile number."),
            ("560001", "A 6-digit PIN code."),
            ("0", "Zero is written with one digit."),
        ],
        edge=["1", "9", "10", "99", "100", "1000000000000000000", "999999999999999999"],
        gen=lambda r: str(r.randint(0, 10**r.randint(1, 18))),
    ),
    Spec(
        slug="power-calculator",
        title="Power Calculator",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "A bacteria colony multiplies a times every hour. Starting with 1 bacterium, how many will there be after b hours?\n\n"
            "Compute a raised to the power b using a loop. Don't use the built-in power function."
        ),
        input_format="A single line with two integers a and b.",
        output_format="Print a^b. Take 0^0 as 1.",
        constraints=["0 ≤ a ≤ 10", "0 ≤ b ≤ 18", "The answer fits in 10^18 (use long long or long)."],
        hints=["Start with result = 1 and multiply by a, b times.", "If b is 0, the loop never runs and the answer is 1."],
        approach=(
            "Power is repeated multiplication, just like multiplication is repeated addition. Run a loop b times, multiplying the result by a each time.\n\n"
            "Later you will learn 'fast power' which needs only about log b steps."
        ),
        time="O(b)", space="O(1)",
        solution='''
a, b = map(int, input().split())
result = 1
for _ in range(b):
    result = result * a
print(result)
''',
        samples=[
            ("2 10", "2 multiplied 10 times = 1024."),
            ("5 0", "Anything to the power 0 is 1."),
            ("3 4", "3 × 3 × 3 × 3 = 81."),
        ],
        edge=["0 0", "0 5", "1 18", "10 18", "7 1", "2 0"],
        gen=_pow_case,
    ),
    Spec(
        slug="even-odd-sum",
        title="Even Sum and Odd Sum",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "Two teams play a counting game: Team Even collects all even numbers from 1 to N and Team Odd collects all odd numbers.\n\n"
            "Print the total each team collects."
        ),
        input_format="A single integer N.",
        output_format="Print two numbers separated by a space: the even sum, then the odd sum.",
        constraints=["1 ≤ N ≤ 10^5"],
        hints=["Use two separate totals and add each number to the right one.", "i % 2 == 0 means i is even."],
        approach=(
            "Loop from 1 to N with two accumulators, and decide where each number goes using the remainder by 2.\n\n"
            "The sums can reach about 2.5 × 10^9, so use long in C, C++ and Java."
        ),
        time="O(N)", space="O(1)",
        solution='''
N = int(input())
even_sum = 0
odd_sum = 0
for i in range(1, N + 1):
    if i % 2 == 0:
        even_sum += i
    else:
        odd_sum += i
print(even_sum, odd_sum)
''',
        samples=[
            ("10", "Evens: 2+4+6+8+10 = 30. Odds: 1+3+5+7+9 = 25."),
            ("1", "Only 1, which is odd."),
            ("5", "Evens: 2+4 = 6. Odds: 1+3+5 = 9."),
        ],
        edge=["2", "3", "100000", "99999"],
        gen=lambda r: str(r.randint(1, 100000)),
    ),
    Spec(
        slug="fibonacci-series",
        title="Fibonacci Series",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "The Fibonacci series appears in sunflower seeds, pinecones and even ancient Indian poetry (Pingala's work).\n\n"
            "The series starts 0, 1 and each next term is the sum of the previous two: 0, 1, 1, 2, 3, 5, 8, …\n"
            "Print the first N terms."
        ),
        input_format="A single integer N.",
        output_format="Print the first N terms separated by single spaces.",
        constraints=["1 ≤ N ≤ 50", "Terms can go above 2^31, so use long long or long."],
        hints=[
            "Keep two variables a = 0 and b = 1. Each step, print a, then move: a, b = b, a + b.",
            "N = 1 should print only 0.",
        ],
        approach=(
            "You only ever need the last two terms to make the next one, so two variables are enough. No list is needed.\n\n"
            "Shift the pair forward N times, recording the first value each time."
        ),
        time="O(N)", space="O(N) for the output",
        solution='''
N = int(input())
a, b = 0, 1
terms = []
for _ in range(N):
    terms.append(str(a))
    a, b = b, a + b
print(" ".join(terms))
''',
        samples=[
            ("7", "0, 1, then 0+1=1, 1+1=2, 1+2=3, 2+3=5, 3+5=8."),
            ("1", "Only the first term."),
            ("2", "The first two terms."),
        ],
        edge=["3", "10", "50", "47", "20"],
        gen=lambda r: str(r.randint(1, 50)),
    ),
    Spec(
        slug="biggest-square-tile",
        title="Biggest Square Tile (GCD)",
        difficulty="easy",
        tags=["Loops", "Math", "GCD"],
        story=(
            "A contractor wants to cover a rectangular floor of size L × B with square tiles, all of the same size, "
            "without cutting any tile.\n\n"
            "Find the side of the biggest square tile that fits perfectly, and how many such tiles are needed.\n"
            "The biggest side is the GCD (greatest common divisor) of L and B."
        ),
        input_format="A single line with two integers L and B.",
        output_format="Print the tile side on the first line and the number of tiles on the second line.",
        constraints=["1 ≤ L, B ≤ 10^6"],
        hints=[
            "Euclid's method: while B is not 0, set L, B = B, L % B. At the end, L is the GCD.",
            "Number of tiles = (L / g) × (B / g).",
        ],
        approach=(
            "The tile side must divide both L and B, and we want the largest such number, which is the GCD.\n\n"
            "Euclid's algorithm (over 2000 years old!) finds it quickly by replacing (a, b) with (b, a % b) until b becomes 0. "
            "Then count how many tiles fit along each side and multiply."
        ),
        time="O(log(min(L, B)))", space="O(1)",
        solution='''
L, B = map(int, input().split())
a, b = L, B
while b != 0:
    a, b = b, a % b
g = a
print(g)
print((L // g) * (B // g))
''',
        samples=[
            ("12 8", "GCD of 12 and 8 is 4. Tiles: (12/4) × (8/4) = 3 × 2 = 6."),
            ("7 5", "7 and 5 share no common factor except 1, so 35 tiles of size 1."),
            ("10 10", "A square floor needs just one big tile."),
        ],
        edge=["1 1", "1 1000000", "1000000 1000000", "999983 2", "720720 360360", "17 34"],
        gen=lambda r: line(r.randint(1, 10**6), r.randint(1, 10**6)),
    ),
    Spec(
        slug="bus-meeting-time",
        title="When Will the Buses Meet? (LCM)",
        difficulty="easy",
        tags=["Loops", "Math", "GCD"],
        story=(
            "At Majestic bus stand, Bus A leaves every a minutes and Bus B leaves every b minutes. Both left together just now.\n\n"
            "After how many minutes will they leave together again? That is the LCM (least common multiple) of a and b."
        ),
        input_format="A single line with two integers a and b.",
        output_format="Print the LCM of a and b.",
        constraints=["1 ≤ a, b ≤ 10^5", "The answer can be up to 10^10. Use long long or long."],
        hints=["LCM × GCD = a × b.", "So LCM = a / GCD × b. Divide first to keep numbers small."],
        approach=(
            "Reuse Euclid's GCD from the previous problem, then use the identity LCM(a, b) = a × b / GCD(a, b).\n\n"
            "Dividing before multiplying (a / g × b) avoids overflow in fixed-size integers."
        ),
        time="O(log(min(a, b)))", space="O(1)",
        solution='''
a, b = map(int, input().split())
x, y = a, b
while y != 0:
    x, y = y, x % y
print(a // x * b)
''',
        samples=[
            ("4 6", "Bus A: 4, 8, 12… Bus B: 6, 12… They meet at 12."),
            ("5 7", "No common factor, so 5 × 7 = 35."),
            ("10 5", "Every time B leaves at a multiple of 10, A also leaves, so 10."),
        ],
        edge=["1 1", "100000 99999", "100000 100000", "1 100000", "12 18", "99991 99989"],
        gen=lambda r: line(r.randint(1, 10**5), r.randint(1, 10**5)),
    ),
    Spec(
        slug="armstrong-number",
        title="Armstrong Number",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "A number is an Armstrong number if the sum of its digits, each raised to the power of the number of digits, equals the number itself.\n\n"
            "Example: 153 has 3 digits, and 1³ + 5³ + 3³ = 1 + 125 + 27 = 153. So 153 is an Armstrong number.\n"
            "Given n, check whether it is an Armstrong number."
        ),
        input_format="A single integer n.",
        output_format="Print Armstrong or Not Armstrong.",
        constraints=["1 ≤ n ≤ 10^9"],
        hints=[
            "First count the digits (call it k).",
            "Then go through each digit d with % 10 and // 10, and add d^k to a total.",
        ],
        approach=(
            "This combines two earlier skills: counting digits, and extracting digits one by one. "
            "Keep a copy of the original number, because you will destroy n while extracting digits.\n\n"
            "Compare the final total with the saved copy."
        ),
        time="O(number of digits)", space="O(1)",
        solution='''
n = int(input())
k = len(str(n))
total = 0
temp = n
while temp > 0:
    d = temp % 10
    total += d ** k
    temp //= 10
if total == n:
    print("Armstrong")
else:
    print("Not Armstrong")
''',
        samples=[
            ("153", "1³ + 5³ + 3³ = 153."),
            ("9474", "4 digits: 9⁴ + 4⁴ + 7⁴ + 4⁴ = 9474."),
            ("123", "1³ + 2³ + 3³ = 36, not 123."),
        ],
        edge=["1", "9", "10", "370", "371", "407", "8208", "548834", "100", "9926315", "999999999"],
        gen=lambda r: str(r.randint(1, 10**6)),
    ),
    Spec(
        slug="perfect-number",
        title="Perfect Number",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "A number is perfect if it equals the sum of its proper divisors (all divisors except the number itself).\n\n"
            "Example: 28 = 1 + 2 + 4 + 7 + 14. Ancient mathematicians loved these rare numbers.\n"
            "Given n, check whether it is perfect."
        ),
        input_format="A single integer n.",
        output_format="Print Perfect or Not Perfect.",
        constraints=["1 ≤ n ≤ 10^6"],
        hints=[
            "Loop i from 1 to n - 1 and add i whenever n % i == 0.",
            "Faster: divisors come in pairs (i, n / i), so you only need to loop till √n.",
        ],
        approach=(
            "The simple way is to try every number below n as a divisor. For 10^6 that's fine.\n\n"
            "The smarter way pairs each divisor i with n / i, so a loop up to √n finds them all. "
            "Remember that 1 is not perfect, because it has no proper divisors."
        ),
        time="O(√n)", space="O(1)",
        solution='''
n = int(input())
total = 0
i = 1
while i * i <= n:
    if n % i == 0:
        total += i
        if i != n // i:
            total += n // i
    i += 1
total -= n  # remove n itself
if total == n:
    print("Perfect")
else:
    print("Not Perfect")
''',
        samples=[
            ("28", "1 + 2 + 4 + 7 + 14 = 28."),
            ("6", "1 + 2 + 3 = 6."),
            ("12", "1 + 2 + 3 + 4 + 6 = 16, not 12."),
        ],
        edge=["1", "2", "496", "8128", "1000000", "999983", "495", "36"],
        gen=lambda r: str(r.randint(1, 10**6)),
    ),
    Spec(
        slug="all-factors",
        title="All Factors of a Number",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "The PT teacher has n students and wants to arrange them in equal rows. "
            "Each possible row size is a factor of n.\n\n"
            "Print all factors of n in increasing order."
        ),
        input_format="A single integer n.",
        output_format="Print all factors of n in increasing order, separated by single spaces.",
        constraints=["1 ≤ n ≤ 10^5"],
        hints=["i is a factor of n if n % i == 0.", "Loop i from 1 to n and collect the factors."],
        approach=(
            "Check every number from 1 to n and keep the ones that divide n exactly. Because you check in increasing order, the output is already sorted.\n\n"
            "Challenge: can you do it in O(√n) and still print in sorted order?"
        ),
        time="O(n)", space="O(number of factors)",
        solution='''
n = int(input())
factors = []
for i in range(1, n + 1):
    if n % i == 0:
        factors.append(str(i))
print(" ".join(factors))
''',
        samples=[
            ("12", "12 can be split as 1, 2, 3, 4, 6 or 12 per row."),
            ("7", "7 is prime, so only 1 and 7."),
            ("1", "1 has only itself."),
        ],
        edge=["2", "36", "100000", "99991", "64", "360"],
        gen=lambda r: str(r.randint(1, 10**5)),
    ),
    Spec(
        slug="digital-root",
        title="Digital Root",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "In numerology, people keep adding the digits of a number until a single digit is left. This is called the digital root.\n\n"
            "Example: 9875 → 9+8+7+5 = 29 → 2+9 = 11 → 1+1 = 2.\n"
            "Given n, find its digital root."
        ),
        input_format="A single integer n.",
        output_format="Print the digital root.",
        constraints=["0 ≤ n ≤ 10^18"],
        hints=[
            "Write the 'sum of digits' logic, then repeat it while the number has more than one digit (n >= 10).",
            "This needs a loop inside a loop.",
        ],
        approach=(
            "The outer loop keeps going while the number is 10 or more. The inner loop computes the sum of digits. "
            "Replace the number by that sum and repeat.\n\n"
            "Fun fact: there is a one-line maths formula, 1 + (n - 1) % 9 for n > 0. Can you see why?"
        ),
        time="O(number of digits)", space="O(1)",
        solution='''
n = int(input())
while n >= 10:
    s = 0
    while n > 0:
        s += n % 10
        n //= 10
    n = s
print(n)
''',
        samples=[
            ("9875", "9875 → 29 → 11 → 2."),
            ("38", "3 + 8 = 11 → 1 + 1 = 2."),
            ("7", "Already a single digit."),
        ],
        edge=["0", "10", "99", "999999999999999999", "1000000000000000000", "123456789"],
        gen=lambda r: str(r.randint(0, 10**r.randint(2, 18))),
    ),
    Spec(
        slug="collatz-steps",
        title="The 3n + 1 Game",
        difficulty="easy",
        tags=["Loops", "Math"],
        story=(
            "Here is a famous puzzle that mathematicians still haven't fully solved:\n"
            "• If n is even, divide it by 2.\n"
            "• If n is odd, make it 3n + 1.\n"
            "Repeat until n becomes 1.\n\n"
            "Given n, count how many steps it takes to reach 1."
        ),
        input_format="A single integer n.",
        output_format="Print the number of steps.",
        constraints=["1 ≤ n ≤ 10^6", "Values in between can exceed 2^31, so use long long or long."],
        hints=["Use a while loop that runs while n != 1.", "Count one step for every change you make to n."],
        approach=(
            "You don't know in advance how many steps there will be, which is exactly when a while loop beats a for loop.\n\n"
            "Simulate the rules and count. If n is already 1, the answer is 0."
        ),
        time="O(steps)", space="O(1)",
        solution='''
n = int(input())
steps = 0
while n != 1:
    if n % 2 == 0:
        n //= 2
    else:
        n = 3 * n + 1
    steps += 1
print(steps)
''',
        samples=[
            ("6", "6 → 3 → 10 → 5 → 16 → 8 → 4 → 2 → 1: 8 steps."),
            ("1", "Already 1, so 0 steps."),
            ("16", "16 → 8 → 4 → 2 → 1: 4 steps."),
        ],
        edge=["2", "3", "27", "97", "837799", "1000000", "871"],
        gen=lambda r: str(r.randint(1, 10**6)),
    ),
    Spec(
        slug="binary-to-decimal",
        title="Binary to Decimal",
        difficulty="easy",
        tags=["Loops", "Math", "Strings"],
        story=(
            "Computers store everything as 0s and 1s. Your friend's electronics project prints numbers in binary, "
            "and you need to read them as normal decimal numbers.\n\n"
            "Each position is a power of 2 from the right: 1011 = 1×8 + 0×4 + 1×2 + 1×1 = 11.\n"
            "Given a binary string, print its decimal value."
        ),
        input_format="A single line containing a binary string (only 0 and 1).",
        output_format="Print the decimal value.",
        constraints=["1 ≤ length ≤ 30", "The string has no leading zeros unless it is exactly 0."],
        hints=[
            "Read the string left to right: value = value × 2 + current bit.",
            "Convert the character '1' to the number 1 (in C: ch - '0').",
        ],
        approach=(
            "Reading left to right, each new bit doubles everything seen so far and then adds itself. "
            "This is the same way we read decimal numbers (×10), only with 2.\n\n"
            "Try it without any built-in conversion function."
        ),
        time="O(length)", space="O(1)",
        solution='''
s = input().strip()
value = 0
for ch in s:
    value = value * 2 + (ord(ch) - ord("0"))
print(value)
''',
        samples=[
            ("1011", "8 + 0 + 2 + 1 = 11."),
            ("0", "Zero is zero in every base."),
            ("11111111", "Eight 1s = 255, the largest value in one byte."),
        ],
        edge=["1", "10", "100", "1" * 30, "1" + "0" * 29, "1010101010"],
        gen=_binary,
    ),
    Spec(
        slug="decimal-to-binary",
        title="Decimal to Binary",
        difficulty="easy",
        tags=["Loops", "Math", "Strings"],
        story=(
            "Now let's go the other way. Convert a normal decimal number into binary.\n\n"
            "Keep dividing by 2 and note the remainders. Reading the remainders from bottom to top gives the binary form."
        ),
        input_format="A single integer n.",
        output_format="Print the binary representation of n without leading zeros. For 0 print 0.",
        constraints=["0 ≤ n ≤ 10^9"],
        hints=[
            "n % 2 gives the last binary digit, and n // 2 removes it.",
            "The digits come out in reverse order, so reverse them at the end.",
        ],
        approach=(
            "Repeated division by 2 peels off binary digits from the right. Collect them and reverse.\n\n"
            "Handle 0 separately, because the loop would produce an empty string."
        ),
        time="O(log n)", space="O(log n)",
        solution='''
n = int(input())
if n == 0:
    print(0)
else:
    bits = []
    while n > 0:
        bits.append(str(n % 2))
        n //= 2
    print("".join(reversed(bits)))
''',
        samples=[
            ("11", "11 → 1, 5 → 1, 2 → 0, 1 → 1. Reversed: 1011."),
            ("0", "Zero stays 0."),
            ("8", "8 is a power of two: 1000."),
        ],
        edge=["1", "2", "255", "256", "1000000000", "1023", "1024"],
        gen=lambda r: str(r.randint(0, 10**r.randint(1, 9))),
    ),

    # ───────────────────────── Stage 4: Patterns ─────────────────────────
    Spec(
        slug="star-staircase",
        title="Star Staircase",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Patterns are the gym for your loop muscles. Let's build a staircase of stars.\n\n"
            "Given N, print N rows: row 1 has 1 star, row 2 has 2 stars, and so on up to row N with N stars."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i has exactly i '*' characters with no spaces.",
        constraints=["1 ≤ N ≤ 50"],
        hints=["The outer loop picks the row i, and the inner loop prints i stars.", "Move to a new line after each row."],
        approach=(
            "Every pattern problem is answered by one question: for row i, what exactly do I print? "
            "Here the answer is i stars.\n\n"
            "The outer loop handles rows and the inner loop handles the content of each row."
        ),
        time="O(N²)", space="O(1)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    print("*" * i)
''',
        samples=[
            ("3", "Row 1: one star. Row 2: two stars. Row 3: three stars."),
            ("1", "Just one star."),
            ("5", "Five rows, growing by one star each."),
        ],
        edge=["2", "50", "10", "25"],
        gen=lambda r: str(r.randint(1, 50)),
    ),
    Spec(
        slug="melting-ice-candy",
        title="Melting Ice Candy",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Your ice candy melts one bite at a time on a hot summer day. "
            "Print an upside-down star triangle: the first row has N stars, the next has N-1, down to 1 star."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i (starting from 1) has N - i + 1 stars with no spaces.",
        constraints=["1 ≤ N ≤ 50"],
        hints=["Run the row loop backwards from N to 1.", "Or keep i going forward and print N - i + 1 stars."],
        approach=(
            "This is the same as the staircase, but the count shrinks. "
            "You can either reverse the loop, or compute the count from the row number. Both are worth trying."
        ),
        time="O(N²)", space="O(1)",
        solution='''
N = int(input())
for i in range(N, 0, -1):
    print("*" * i)
''',
        samples=[
            ("4", "4 stars, then 3, then 2, then 1."),
            ("1", "A single star."),
            ("3", "3, 2, 1 stars."),
        ],
        edge=["2", "50", "7", "20"],
        gen=lambda r: str(r.randint(1, 50)),
    ),
    Spec(
        slug="number-staircase",
        title="Number Staircase",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Kids learn counting with a number staircase. Row i shows the numbers 1 to i.\n\n"
            "Given N, print N rows."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i contains the numbers 1 to i separated by single spaces.",
        constraints=["1 ≤ N ≤ 30"],
        hints=["The inner loop goes from 1 to i and prints j, not a star.", "Join the numbers with spaces, with no trailing space."],
        approach=(
            "Now the inner loop prints its own counter instead of a fixed symbol. "
            "This small change, printing the loop variable, is the key to all number patterns."
        ),
        time="O(N²)", space="O(N)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    row = []
    for j in range(1, i + 1):
        row.append(str(j))
    print(" ".join(row))
''',
        samples=[
            ("4", "Each row counts from 1 up to its row number."),
            ("1", "Only the number 1."),
            ("2", "Row 1: 1. Row 2: 1 2."),
        ],
        edge=["3", "30", "10", "15"],
        gen=lambda r: str(r.randint(1, 30)),
    ),
    Spec(
        slug="floyds-triangle",
        title="Floyd's Triangle",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Floyd's triangle fills rows with consecutive numbers: row 1 has 1 number, row 2 has 2 numbers, and the counting never restarts.\n\n"
            "1\n2 3\n4 5 6\n…\nGiven N, print the first N rows."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i has i consecutive numbers separated by single spaces.",
        constraints=["1 ≤ N ≤ 30"],
        hints=[
            "Keep one counter outside both loops, starting at 1.",
            "Print the counter and increase it every time the inner loop runs.",
        ],
        approach=(
            "The difference from the number staircase is that the counter lives outside the loops, so it keeps increasing across rows.\n\n"
            "Where a variable is declared decides how long it lives, and this problem shows why that matters."
        ),
        time="O(N²)", space="O(N)",
        solution='''
N = int(input())
num = 1
for i in range(1, N + 1):
    row = []
    for _ in range(i):
        row.append(str(num))
        num += 1
    print(" ".join(row))
''',
        samples=[
            ("4", "Numbers 1 to 10 filled row by row."),
            ("1", "Only 1."),
            ("3", "1 / 2 3 / 4 5 6."),
        ],
        edge=["2", "30", "10", "14"],
        gen=lambda r: str(r.randint(1, 30)),
    ),
    Spec(
        slug="star-pyramid",
        title="Star Pyramid",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Let's build a proper pyramid like the temple gopuram. Row i has 2i - 1 stars, centred using spaces on the left.\n\n"
            "For N = 3, the top row is 2 spaces and 1 star, the middle row is 1 space and 3 stars, and the base is 5 stars. "
            "See Example 1 for the exact shape."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i has N - i spaces followed by 2i - 1 stars. Do not print spaces after the stars.",
        constraints=["1 ≤ N ≤ 40"],
        hints=["Each row has two parts: leading spaces (N - i) and stars (2i - 1).", "Never add spaces after the last star."],
        approach=(
            "Break each row into parts and work out a formula for each part using the row number. "
            "Spaces decrease by one per row while stars increase by two.\n\n"
            "Write a small table (row, spaces, stars) on paper first. Trainers call this 'pattern tabulation'."
        ),
        time="O(N²)", space="O(1)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    print(" " * (N - i) + "*" * (2 * i - 1))
''',
        samples=[
            ("3", "Row 1: 2 spaces + 1 star. Row 2: 1 space + 3 stars. Row 3: 0 spaces + 5 stars."),
            ("1", "A single star."),
            ("5", "A 5-row pyramid with 9 stars at the base."),
        ],
        edge=["2", "40", "10", "4"],
        gen=lambda r: str(r.randint(1, 40)),
    ),
    Spec(
        slug="hollow-square-frame",
        title="Hollow Square Photo Frame",
        difficulty="easy",
        tags=["Patterns", "Nested Loops", "Conditionals"],
        story=(
            "A photo frame has a border but is empty inside. Print an N × N square where the border is made of stars and the inside is spaces."
        ),
        input_format="A single integer N.",
        output_format="Print N lines of exactly N characters. Border cells are '*' and inner cells are spaces.",
        constraints=["1 ≤ N ≤ 50"],
        hints=[
            "A cell (i, j) is on the border if i is the first or last row, or j is the first or last column.",
            "Use an if inside the inner loop to choose between '*' and ' '.",
        ],
        approach=(
            "Now the inner loop makes a decision for every cell. "
            "Border cells satisfy i == 1, i == N, j == 1 or j == N.\n\n"
            "Since the last column is always a star, no line ends with a space."
        ),
        time="O(N²)", space="O(N)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    row = ""
    for j in range(1, N + 1):
        if i == 1 or i == N or j == 1 or j == N:
            row += "*"
        else:
            row += " "
    print(row)
''',
        samples=[
            ("4", "The first and last rows are full. Middle rows have stars only at the edges."),
            ("1", "A 1 × 1 frame is just one star."),
            ("2", "A 2 × 2 frame has no inside, so all stars."),
        ],
        edge=["3", "50", "5", "10"],
        gen=lambda r: str(r.randint(1, 50)),
    ),
    Spec(
        slug="alphabet-staircase",
        title="Alphabet Staircase",
        difficulty="easy",
        tags=["Patterns", "Nested Loops", "Strings"],
        story=(
            "A nursery teacher is making an ABC chart. Row 1 shows A, row 2 shows AB, row 3 shows ABC, and so on.\n\n"
            "Given N, print N rows."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i contains the first i capital letters with no spaces.",
        constraints=["1 ≤ N ≤ 26"],
        hints=[
            "Letters are numbers inside the computer. 'A' + 1 is 'B'.",
            "In Python use chr(ord('A') + j). In C or Java use (char)('A' + j).",
        ],
        approach=(
            "Same skeleton as the number staircase, but each number is converted to a letter by adding it to the code of 'A'.\n\n"
            "This idea of character arithmetic is used later in Caesar ciphers and frequency counting."
        ),
        time="O(N²)", space="O(N)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    row = ""
    for j in range(i):
        row += chr(ord("A") + j)
    print(row)
''',
        samples=[
            ("4", "A, AB, ABC, ABCD."),
            ("1", "Just A."),
            ("26", "All the way to the full alphabet."),
        ],
        edge=["2", "3", "10", "25"],
        gen=lambda r: str(r.randint(1, 26)),
    ),
    Spec(
        slug="diamond-pattern",
        title="Diamond Pattern",
        difficulty="easy",
        tags=["Patterns", "Nested Loops"],
        story=(
            "Combine what you've learned to print a diamond, a pyramid on top of an upside-down pyramid.\n\n"
            "For N = 3 the rows have 1, 3, 5, 3 and 1 stars, each centred with spaces on the left. "
            "See Example 1 for the exact shape."
        ),
        input_format="A single integer N (the number of rows in the top half, including the middle row).",
        output_format="Print 2N - 1 lines. Do not print spaces after the stars.",
        constraints=["1 ≤ N ≤ 30"],
        hints=[
            "The top half is exactly the star pyramid from before.",
            "The bottom half is the same pyramid printed in reverse, without repeating the middle row.",
        ],
        approach=(
            "Break the big shape into two shapes you already know. "
            "Print the pyramid for rows 1 to N, then rows N-1 down to 1 with the same formula.\n\n"
            "Reusing an earlier solution as a building block is how real programmers work."
        ),
        time="O(N²)", space="O(1)",
        solution='''
N = int(input())
for i in range(1, N + 1):
    print(" " * (N - i) + "*" * (2 * i - 1))
for i in range(N - 1, 0, -1):
    print(" " * (N - i) + "*" * (2 * i - 1))
''',
        samples=[
            ("3", "Pyramid of 3 rows, then 2 rows shrinking back."),
            ("1", "Just one star."),
            ("2", "Three lines: 1, 3 and 1 stars."),
        ],
        edge=["4", "30", "10", "5"],
        gen=lambda r: str(r.randint(1, 30)),
    ),
]
