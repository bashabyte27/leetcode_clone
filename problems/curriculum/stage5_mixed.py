"""Stage 7 (89-100): hashing, matrices and capstone problems."""

from .base import Spec, array_input, line, rand_list


def _matrix(r, rows, cols, lo, hi):
    return [[r.randint(lo, hi) for _ in range(cols)] for _ in range(rows)]


def _matrix_text(m):
    return "\n".join(line(*row) for row in m)


def _rc_case(lo=-50, hi=50, max_r=6, max_c=6):
    def gen(r):
        rows, cols = r.randint(1, max_r), r.randint(1, max_c)
        return f"{rows} {cols}\n{_matrix_text(_matrix(r, rows, cols, lo, hi))}"
    return gen


def _square_case(r):
    n = r.randint(1, 7)
    return f"{n}\n{_matrix_text(_matrix(r, n, n, -20, 20))}"


def _add_case(r):
    rows, cols = r.randint(1, 5), r.randint(1, 5)
    a, b = _matrix(r, rows, cols, -100, 100), _matrix(r, rows, cols, -100, 100)
    return f"{rows} {cols}\n{_matrix_text(a)}\n{_matrix_text(b)}"


def _majority_case(r):
    n = r.randint(1, 25)
    if r.random() < 0.6:
        winner = r.randint(1, 5)
        k = n // 2 + 1
        votes = [winner] * k + [r.randint(1, 5) for _ in range(n - k)]
    else:
        votes = [r.randint(1, 4) for _ in range(n)]
    r.shuffle(votes)
    return array_input(votes)


def _duplicate_case(r):
    n = r.randint(1, 40)
    nums = list(range(1, n + 1)) + [r.randint(1, n)]
    r.shuffle(nums)
    return f"{n}\n{line(*nums)}"


def _bsearch_case(r):
    a = sorted(r.sample(range(-200, 200), r.randint(1, 40)))
    x = r.choice(a) if r.random() < 0.6 else r.randint(-210, 210)
    return array_input(a) + f"\n{x}"


def _pairs_case(r):
    a = rand_list(r, 1, 25, -10, 10)
    return array_input(a) + f"\n{r.randint(-10, 10)}"


ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _to_roman(n):
    out = ""
    for value, sym in ROMAN:
        while n >= value:
            out += sym
            n -= value
    return out


SPECS = [
    Spec(
        slug="class-monitor-election",
        title="Class Monitor Election (Majority Vote)",
        difficulty="easy",
        tags=["Arrays", "Hashing"],
        story=(
            "To become class monitor, a candidate needs more than half of all votes, a strict majority.\n\n"
            "Given all the votes (candidate numbers), print the winner. If nobody has a strict majority, print No Majority."
        ),
        input_format="The first line has n, the number of votes.\nThe second line has n candidate numbers.",
        output_format="Print the winning candidate's number, or No Majority.",
        constraints=["1 ≤ n ≤ 10^5", "1 ≤ candidate ≤ 10^9"],
        hints=[
            "Count each candidate's votes with a dictionary.",
            "A winner needs count > n / 2. Be careful, exactly half is not enough.",
        ],
        approach=(
            "Count votes per candidate with a hash map, then look for a count above n / 2. At most one candidate can have it.\n\n"
            "Bonus: the Boyer-Moore voting algorithm finds a majority with O(1) memory. Look it up after you solve this."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
votes = list(map(int, input().split()))
count = {}
for v in votes:
    count[v] = count.get(v, 0) + 1
winner = None
for v, c in count.items():
    if c > n // 2:
        winner = v
print(winner if winner is not None else "No Majority")
''',
        samples=[
            ("7\n2 2 1 1 1 2 2", "Candidate 2 got 4 of 7 votes, more than half."),
            ("4\n1 1 2 2", "Each has exactly half, which is not a strict majority."),
            ("1\n5", "The only vote decides it."),
        ],
        edge=[array_input([3, 3, 4]), array_input([1, 2, 3]), array_input([1000000000] * 5)],
        gen=_majority_case,
    ),
    Spec(
        slug="report-card-totals",
        title="Report Card Totals",
        difficulty="easy",
        tags=["Matrix", "Arrays"],
        story=(
            "A class teacher has a marks table: each row is a student and each column is a subject.\n\n"
            "Print the total marks of every student."
        ),
        input_format="The first line has r (students) and c (subjects).\nEach of the next r lines has c integers.",
        output_format="Print r lines. Line i is the total of row i.",
        constraints=["1 ≤ r, c ≤ 100", "0 ≤ marks ≤ 100"],
        hints=["Read the table row by row.", "For each row, add up its c values and print the sum."],
        approach=(
            "Welcome to 2D arrays (matrices)! A matrix is a list of rows, and each row is a list.\n\n"
            "Reading it is just reading r lines of numbers. Summing each row is the familiar total pattern, applied once per row."
        ),
        time="O(r × c)", space="O(r × c)",
        solution='''
r, c = map(int, input().split())
for _ in range(r):
    row = list(map(int, input().split()))
    print(sum(row))
''',
        samples=[
            ("3 4\n90 85 70 60\n100 100 95 90\n40 55 35 50", "Row totals: 305, 385 and 180."),
            ("1 3\n50 60 70", "One student, three subjects."),
            ("2 1\n99\n0", "One subject, two students."),
        ],
        edge=["1 1\n0", "1 1\n100"],
        gen=_rc_case(0, 100),
    ),
    Spec(
        slug="matrix-transpose",
        title="Rotate the Seating Chart (Transpose)",
        difficulty="easy",
        tags=["Matrix"],
        story=(
            "The seating chart was written row-wise, but the principal wants it column-wise. "
            "That means flipping the matrix over its diagonal: row i becomes column i.\n\n"
            "Print the transpose of the given matrix."
        ),
        input_format="The first line has r and c.\nEach of the next r lines has c integers.",
        output_format="Print c lines, each with r integers separated by spaces: the transposed matrix.",
        constraints=["1 ≤ r, c ≤ 100", "-1000 ≤ value ≤ 1000"],
        hints=["The element at (i, j) moves to (j, i).", "The outer loop goes over columns j and the inner loop goes over rows i."],
        approach=(
            "The transpose has its dimensions swapped (c × r). New row j is old column j, so read down each column of the original and print it as a row.\n\n"
            "Getting the loop order right is the whole lesson here."
        ),
        time="O(r × c)", space="O(r × c)",
        solution='''
r, c = map(int, input().split())
m = [list(map(int, input().split())) for _ in range(r)]
for j in range(c):
    row = []
    for i in range(r):
        row.append(str(m[i][j]))
    print(" ".join(row))
''',
        samples=[
            ("2 3\n1 2 3\n4 5 6", "Columns (1,4), (2,5), (3,6) become rows."),
            ("1 3\n7 8 9", "A single row becomes a single column."),
            ("2 2\n1 2\n3 4", "1 and 4 stay, while 2 and 3 swap places."),
        ],
        edge=["1 1\n5", "3 1\n1\n2\n3"],
        gen=_rc_case(),
    ),
    Spec(
        slug="diagonal-sum",
        title="Diagonal Sum of a Square Board",
        difficulty="easy",
        tags=["Matrix"],
        story=(
            "On a square game board, special points sit on both diagonals: the main diagonal (top-left to bottom-right) "
            "and the other diagonal (top-right to bottom-left).\n\n"
            "Find the sum of all cells on both diagonals. If n is odd, the centre cell lies on both, so count it only once."
        ),
        input_format="The first line has n.\nEach of the next n lines has n integers.",
        output_format="Print the diagonal sum.",
        constraints=["1 ≤ n ≤ 100", "-1000 ≤ value ≤ 1000"],
        hints=[
            "The main diagonal is m[i][i] and the other diagonal is m[i][n - 1 - i].",
            "When i == n - 1 - i, it is the same cell, so don't add it twice.",
        ],
        approach=(
            "One loop over i covers both diagonals: add m[i][i] and m[i][n-1-i]. "
            "The only catch is the shared centre cell in odd-sized boards.\n\n"
            "This is LeetCode #1572. Index formulas like n - 1 - i will show up again and again."
        ),
        time="O(n)", space="O(n²)",
        solution='''
n = int(input())
m = [list(map(int, input().split())) for _ in range(n)]
total = 0
for i in range(n):
    total += m[i][i]
    if i != n - 1 - i:
        total += m[i][n - 1 - i]
print(total)
''',
        samples=[
            ("3\n1 2 3\n4 5 6\n7 8 9", "1 + 5 + 9 + 3 + 7 = 25. The centre 5 is counted once."),
            ("2\n1 2\n3 4", "1 + 4 + 2 + 3 = 10."),
            ("1\n7", "A single cell is on both diagonals, counted once."),
        ],
        edge=["4\n1 1 1 1\n1 1 1 1\n1 1 1 1\n1 1 1 1"],
        gen=_square_case,
    ),
    Spec(
        slug="matrix-addition",
        title="Add Two Sales Tables",
        difficulty="easy",
        tags=["Matrix"],
        story=(
            "A shop has two branches. Each branch keeps a table of items sold: rows are days and columns are products. "
            "The owner wants the combined table.\n\n"
            "Add the two matrices cell by cell."
        ),
        input_format="The first line has r and c.\nThe next r lines are matrix A.\nThe next r lines are matrix B.",
        output_format="Print r lines with c integers each: A + B.",
        constraints=["1 ≤ r, c ≤ 100", "-1000 ≤ value ≤ 1000"],
        hints=["Read A fully, then B.", "Cell (i, j) of the answer is A[i][j] + B[i][j]."],
        approach=(
            "Two nested loops visit every cell position and add the matching cells. "
            "Matrices must have the same shape to be added, and here they always do."
        ),
        time="O(r × c)", space="O(r × c)",
        solution='''
r, c = map(int, input().split())
A = [list(map(int, input().split())) for _ in range(r)]
B = [list(map(int, input().split())) for _ in range(r)]
for i in range(r):
    print(" ".join(str(A[i][j] + B[i][j]) for j in range(c)))
''',
        samples=[
            ("2 2\n1 2\n3 4\n5 6\n7 8", "1+5, 2+6, 3+7, 4+8."),
            ("1 3\n10 20 30\n-10 -20 -30", "Everything cancels out to 0."),
            ("2 1\n5\n6\n1\n1", "Column matrices: 6 and 7."),
        ],
        edge=["1 1\n1000\n1000", "1 1\n-1000\n-1000"],
        gen=_add_case,
    ),
    Spec(
        slug="find-the-duplicate-token",
        title="Find the Duplicate Token",
        difficulty="medium",
        tags=["Arrays", "Hashing"],
        story=(
            "A hospital gives tokens numbered 1 to n. By mistake, one token number was printed twice, so there are n + 1 tokens.\n\n"
            "Find the token number that appears twice."
        ),
        input_format="The first line has n.\nThe second line has n + 1 integers, each from 1 to n.",
        output_format="Print the duplicated number.",
        constraints=["1 ≤ n ≤ 10^5", "Exactly one number appears twice, and every other number appears once."],
        hints=[
            "Keep a set of numbers you've seen. The first number already in the set is the answer.",
            "Maths trick: sum of all tokens - (1 + 2 + … + n) = the duplicate.",
        ],
        approach=(
            "With a 'seen' set, the first repeat you meet is the answer, in O(n) time and O(n) memory.\n\n"
            "Because every number from 1 to n appears exactly once except the duplicate, the sum trick also works in O(1) memory. "
            "Compare it with the missing roll number problem."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
tokens = list(map(int, input().split()))
seen = set()
for t in tokens:
    if t in seen:
        print(t)
        break
    seen.add(t)
''',
        samples=[
            ("4\n1 3 4 2 2", "Token 2 appears twice."),
            ("1\n1 1", "Only one token number, printed twice."),
            ("5\n5 1 2 5 3 4", "Token 5 is the repeat."),
        ],
        edge=["2\n2 1 2", "3\n1 1 2 3"],
        gen=_duplicate_case,
    ),
    Spec(
        slug="binary-search-dictionary",
        title="Dictionary Search (Binary Search)",
        difficulty="medium",
        tags=["Arrays", "Searching", "Binary Search"],
        story=(
            "When you look up a word in a dictionary, you don't read page by page. "
            "You open the middle and decide whether to go left or right. That's binary search!\n\n"
            "Given a sorted list of distinct numbers, find the index (0-based) of x, or print -1 if it isn't there."
        ),
        input_format="The first line has n.\nThe second line has n distinct integers in increasing order.\nThe third line has x.",
        output_format="Print the index of x, or -1.",
        constraints=["1 ≤ n ≤ 10^5", "-10^9 ≤ value, x ≤ 10^9"],
        hints=[
            "Keep low = 0 and high = n - 1. Look at mid = (low + high) // 2.",
            "If a[mid] < x, search the right half (low = mid + 1). If it's bigger, search the left half (high = mid - 1).",
        ],
        approach=(
            "Each comparison throws away half of the remaining list, so even 10^5 elements need only about 17 checks. Linear search could need 100,000.\n\n"
            "Be careful with the loop condition (low <= high) and with updating low and high so the loop always moves. "
            "This is LeetCode #704, and one of the most important algorithms you'll learn."
        ),
        time="O(log n)", space="O(n) for input",
        solution='''
n = int(input())
a = list(map(int, input().split()))
x = int(input())
low, high = 0, n - 1
answer = -1
while low <= high:
    mid = (low + high) // 2
    if a[mid] == x:
        answer = mid
        break
    elif a[mid] < x:
        low = mid + 1
    else:
        high = mid - 1
print(answer)
''',
        samples=[
            ("6\n-1 0 3 5 9 12\n9", "9 is at index 4."),
            ("6\n-1 0 3 5 9 12\n2", "2 is not in the list."),
            ("1\n5\n5", "A single element that matches."),
        ],
        edge=["1\n5\n4", "2\n1 2\n1", "2\n1 2\n2", "5\n10 20 30 40 50\n60", "5\n10 20 30 40 50\n5"],
        gen=_bsearch_case,
    ),
    Spec(
        slug="count-pairs-with-sum",
        title="Count Friend Pairs With Target Sum",
        difficulty="medium",
        tags=["Arrays", "Hashing"],
        story=(
            "For a team game, pairs of students are formed whose skill points add up to exactly k.\n\n"
            "Count the number of index pairs (i, j) with i < j and a[i] + a[j] = k."
        ),
        input_format="The first line has n.\nThe second line has n integers.\nThe third line has k.",
        output_format="Print the number of pairs.",
        constraints=["1 ≤ n ≤ 10^5", "-10^9 ≤ value, k ≤ 10^9", "The answer can be large, so use long long or long."],
        hints=[
            "Brute force with two loops is O(n²), too slow for 10^5.",
            "Scan left to right with a count map. For each a[j], add how many times k - a[j] has appeared before, then record a[j].",
        ],
        approach=(
            "This extends Two Sum: instead of finding one pair, count all of them. "
            "Before adding a[j] to the map, every earlier occurrence of k - a[j] forms a valid pair with it.\n\n"
            "Recording a[j] after counting means i < j automatically and an element never pairs with itself."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
k = int(input())
seen = {}
pairs = 0
for x in a:
    pairs += seen.get(k - x, 0)
    seen[x] = seen.get(x, 0) + 1
print(pairs)
''',
        samples=[
            ("5\n1 5 7 -1 5\n6", "Pairs: (1,5), (1,5) with the second 5, and (7,-1). Total 3."),
            ("4\n1 1 1 1\n2", "Every pair of the four 1s works: 6 pairs."),
            ("3\n1 2 3\n10", "No pair adds up to 10."),
        ],
        edge=[array_input([5]) + "\n10", array_input([5, 5]) + "\n10", array_input([0] * 10) + "\n0"],
        gen=_pairs_case,
    ),
    Spec(
        slug="happy-number",
        title="Happy Number",
        difficulty="easy",
        tags=["Math", "Hashing"],
        story=(
            "Take a number, replace it with the sum of the squares of its digits, and repeat. "
            "If you eventually reach 1, the number is happy. If you get stuck in a loop that never reaches 1, it's not.\n\n"
            "Example: 19 → 1² + 9² = 82 → 68 → 100 → 1. So 19 is happy."
        ),
        input_format="A single integer n.",
        output_format="Print Happy or Not Happy.",
        constraints=["1 ≤ n ≤ 10^9"],
        hints=[
            "How do you know you're stuck? You'll see a number you've seen before.",
            "Keep a set of seen numbers and stop when you reach 1 or a repeat.",
        ],
        approach=(
            "Simulate the process and remember every number in a set. Reaching 1 means happy, and revisiting a number means we're in a cycle forever.\n\n"
            "Using a set to detect cycles is a powerful idea, and it reuses your digit-extraction skills. This is LeetCode #202."
        ),
        time="O(log n) per step", space="O(number of steps)",
        solution='''
n = int(input())
seen = set()
while n != 1 and n not in seen:
    seen.add(n)
    total = 0
    while n > 0:
        d = n % 10
        total += d * d
        n //= 10
    n = total
print("Happy" if n == 1 else "Not Happy")
''',
        samples=[
            ("19", "19 → 82 → 68 → 100 → 1."),
            ("2", "2 → 4 → 16 → 37 → … loops forever without reaching 1."),
            ("1", "Already 1."),
        ],
        edge=["7", "4", "10", "100", "1000000000", "999999999", "13", "20"],
        gen=lambda r: str(r.randint(1, 10**r.randint(1, 9))),
    ),
    Spec(
        slug="roman-to-integer",
        title="Roman Numerals to Number",
        difficulty="medium",
        tags=["Strings", "Hashing", "Math"],
        story=(
            "Old clock towers and movie credits use Roman numerals: I=1, V=5, X=10, L=50, C=100, D=500, M=1000.\n\n"
            "Usually symbols are added (VI = 6), but a smaller symbol before a bigger one is subtracted (IV = 4, IX = 9, XL = 40, CM = 900).\n"
            "Convert the Roman numeral to a normal number."
        ),
        input_format="A single valid Roman numeral in capital letters.",
        output_format="Print its value.",
        constraints=["The value is between 1 and 3999."],
        hints=[
            "Store each symbol's value in a dictionary.",
            "If a symbol's value is less than the next symbol's value, subtract it. Otherwise add it.",
        ],
        approach=(
            "Scan left to right and look one step ahead. A smaller value before a bigger one means subtraction, otherwise addition.\n\n"
            "This look-ahead rule handles all six subtraction cases without listing them. This is LeetCode #13."
        ),
        time="O(length)", space="O(1)",
        solution='''
s = input().strip()
value = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
total = 0
for i in range(len(s)):
    if i + 1 < len(s) and value[s[i]] < value[s[i + 1]]:
        total -= value[s[i]]
    else:
        total += value[s[i]]
print(total)
''',
        samples=[
            ("XIV", "X (10) + IV (4) = 14."),
            ("MCMXCIV", "M (1000) + CM (900) + XC (90) + IV (4) = 1994."),
            ("III", "1 + 1 + 1 = 3."),
            ("LVIII", "L (50) + V (5) + III (3) = 58."),
        ],
        edge=["I", "IV", "IX", "XL", "XC", "CD", "CM", "MMMCMXCIX", "MMXXVI"],
        gen=lambda r: _to_roman(r.randint(1, 3999)),
    ),
    Spec(
        slug="pascals-triangle",
        title="Pascal's Triangle",
        difficulty="easy",
        tags=["Arrays", "Patterns", "Math"],
        story=(
            "Pascal's triangle (known in India much earlier as Meru Prastara, from Pingala's work) starts with 1. "
            "Each number below is the sum of the two numbers just above it.\n\n"
            "1\n1 1\n1 2 1\n1 3 3 1\n…\nPrint the first N rows."
        ),
        input_format="A single integer N.",
        output_format="Print N lines. Line i has the i numbers of row i, separated by single spaces (no leading spaces).",
        constraints=["1 ≤ N ≤ 30"],
        hints=[
            "Each row starts and ends with 1.",
            "Inner element j of a new row = previous_row[j - 1] + previous_row[j].",
        ],
        approach=(
            "Build each row from the previous one. This is your first taste of dynamic programming: "
            "solving a bigger problem from answers you have already computed.\n\n"
            "Row 30 has values up to about 7.7 × 10^7, which fits in a normal int. This is LeetCode #118."
        ),
        time="O(N²)", space="O(N)",
        solution='''
N = int(input())
row = [1]
for i in range(N):
    print(" ".join(map(str, row)))
    new_row = [1]
    for j in range(1, len(row)):
        new_row.append(row[j - 1] + row[j])
    new_row.append(1)
    row = new_row
''',
        samples=[
            ("5", "Each inner number is the sum of the two above it."),
            ("1", "Just the top 1."),
            ("3", "1 / 1 1 / 1 2 1."),
        ],
        edge=["2", "30", "10", "4"],
        gen=lambda r: str(r.randint(1, 30)),
    ),
    Spec(
        slug="spiral-matrix",
        title="Spiral Walk in the Garden",
        difficulty="medium",
        tags=["Matrix", "Simulation"],
        story=(
            "A gardener waters a rectangular field of plants in a spiral: starting from the top-left corner, "
            "she walks right, then down, then left, then up, moving one layer inward each round.\n\n"
            "Print the plant numbers in the order she waters them. This is your final boss for this level. You've got this!"
        ),
        input_format="The first line has r and c.\nEach of the next r lines has c integers.",
        output_format="Print all r × c values in spiral order, separated by single spaces.",
        constraints=["1 ≤ r, c ≤ 100", "-1000 ≤ value ≤ 1000"],
        hints=[
            "Keep four boundaries: top, bottom, left, right.",
            "Walk right along top (then top += 1), down along right (right -= 1), left along bottom (bottom -= 1), up along left (left += 1). "
            "Check the boundaries before the left and up walks so that single rows or columns aren't printed twice.",
        ],
        approach=(
            "Simulate the walk with four shrinking boundaries. After finishing each side, move that boundary inward.\n\n"
            "The tricky part is matrices with one leftover row or column. Re-check top <= bottom and left <= right before walking back. "
            "This is LeetCode #54. If you can solve this one, you are ready for the next level."
        ),
        time="O(r × c)", space="O(r × c)",
        solution='''
r, c = map(int, input().split())
m = [list(map(int, input().split())) for _ in range(r)]
top, bottom, left, right = 0, r - 1, 0, c - 1
order = []
while top <= bottom and left <= right:
    for j in range(left, right + 1):
        order.append(m[top][j])
    top += 1
    for i in range(top, bottom + 1):
        order.append(m[i][right])
    right -= 1
    if top <= bottom:
        for j in range(right, left - 1, -1):
            order.append(m[bottom][j])
        bottom -= 1
    if left <= right:
        for i in range(bottom, top - 1, -1):
            order.append(m[i][left])
        left += 1
print(" ".join(map(str, order)))
''',
        samples=[
            ("3 3\n1 2 3\n4 5 6\n7 8 9", "Right 1 2 3, down 6 9, left 8 7, up 4, then the centre 5."),
            ("3 4\n1 2 3 4\n5 6 7 8\n9 10 11 12", "The outer ring first, then the inner part 6 7."),
            ("1 4\n1 2 3 4", "A single row is just read left to right."),
            ("3 1\n1\n2\n3", "A single column is read top to bottom."),
        ],
        edge=["1 1\n42", "2 2\n1 2\n3 4", "4 4\n1 2 3 4\n5 6 7 8\n9 10 11 12\n13 14 15 16"],
        gen=_rc_case(-99, 99, 7, 7),
    ),
]
