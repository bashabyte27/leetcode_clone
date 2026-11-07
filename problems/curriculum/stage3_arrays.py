"""Stage 5 (49-70): arrays / lists."""

from .base import Spec, array_input, line, rand_list


def _arr(lo_n, hi_n, lo_v, hi_v):
    return lambda r: array_input(rand_list(r, lo_n, hi_n, lo_v, hi_v))


def _search_case(r):
    a = rand_list(r, 1, 30, 1, 50)
    x = r.choice(a) if r.random() < 0.6 else r.randint(1, 60)
    return array_input(a) + f"\n{x}"


def _rotate_case(r):
    a = rand_list(r, 1, 25, -100, 100)
    return f"{len(a)} {r.randint(0, 60)}\n{line(*a)}"


def _zeros_case(r):
    a = [0 if r.random() < 0.4 else r.randint(-50, 50) for _ in range(r.randint(1, 25))]
    return array_input(a)


def _sorted_case(r):
    return array_input(sorted(rand_list(r, 1, 30, -20, 20)))


def _missing_case(r):
    n = r.randint(2, 60)
    nums = list(range(1, n + 1))
    nums.remove(r.randint(1, n))
    r.shuffle(nums)
    return f"{n}\n{line(*nums)}"


def _two_sum_case(r):
    while True:
        a = rand_list(r, 2, 20, -50, 50)
        i, j = sorted(r.sample(range(len(a)), 2))
        target = a[i] + a[j]
        pairs = [(p, q) for p in range(len(a)) for q in range(p + 1, len(a)) if a[p] + a[q] == target]
        if len(pairs) == 1:
            return array_input(a) + f"\n{target}"


def _bits_case(r):
    p = r.random()
    return array_input([1 if r.random() < p else 0 for _ in range(r.randint(1, 30))])


def _merge_case(r):
    a = sorted(rand_list(r, 1, 15, -30, 30))
    b = sorted(rand_list(r, 1, 15, -30, 30))
    return f"{len(a)} {len(b)}\n{line(*a)}\n{line(*b)}"


def _two_arrays(r):
    a = rand_list(r, 1, 15, 1, 20)
    b = rand_list(r, 1, 15, 1, 20)
    return f"{len(a)} {len(b)}\n{line(*a)}\n{line(*b)}"


def _candies_case(r):
    a = rand_list(r, 1, 15, 1, 100)
    return array_input(a) + f"\n{r.randint(1, 50)}"


SPECS = [
    Spec(
        slug="total-runs-in-an-innings",
        title="Total Runs in an Innings",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "The scorer at your gully cricket match wrote down the runs scored on every ball. "
            "At the end of the innings, everyone wants the total score.\n\n"
            "Given the runs on each ball, print the total."
        ),
        input_format="The first line has n, the number of balls.\nThe second line has n integers, the runs on each ball.",
        output_format="Print the total runs.",
        constraints=["1 ≤ n ≤ 1000", "0 ≤ runs on a ball ≤ 6"],
        hints=["Read all n numbers into a list.", "Start total = 0 and add each element."],
        approach=(
            "Welcome to arrays! First learn to read a whole line of numbers into a list. "
            "Then visit each element once and keep a running total.\n\n"
            "This 'visit every element' loop is the base of almost every array problem."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
runs = list(map(int, input().split()))
total = 0
for r in runs:
    total += r
print(total)
''',
        samples=[
            ("6\n1 4 0 6 2 1", "1 + 4 + 0 + 6 + 2 + 1 = 14 runs in the over."),
            ("3\n0 0 0", "Three dot balls, so the total is 0."),
            ("1\n6", "A single ball hit for six."),
        ],
        edge=[array_input([6] * 1000), array_input([0] * 5 + [1])],
        gen=_arr(1, 60, 0, 6),
    ),
    Spec(
        slug="hottest-and-coldest-day",
        title="Hottest and Coldest Day",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "The weather station in Shimla recorded the temperature every day for n days.\n\n"
            "Find the highest and the lowest temperature."
        ),
        input_format="The first line has n.\nThe second line has n integers, the temperatures.",
        output_format="Print the maximum and the minimum separated by a space.",
        constraints=["1 ≤ n ≤ 1000", "-50 ≤ temperature ≤ 50"],
        hints=[
            "Start max and min with the first element, not with 0. Why?",
            "Visit the rest of the elements and update max and min when needed.",
        ],
        approach=(
            "Keep two 'best so far' values and update them as you scan. "
            "Initialise them with the first element. If you start max at 0, an array of all-negative temperatures would give a wrong answer."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
temps = list(map(int, input().split()))
hi = temps[0]
lo = temps[0]
for t in temps:
    if t > hi:
        hi = t
    if t < lo:
        lo = t
print(hi, lo)
''',
        samples=[
            ("5\n12 -3 8 15 0", "Hottest is 15 and coldest is -3."),
            ("3\n-5 -10 -2", "All negative: max is -2, min is -10."),
            ("1\n25", "With one day, it is both the hottest and the coldest."),
        ],
        edge=[array_input([7, 7, 7, 7]), array_input([50, -50]), array_input([-50] * 3)],
        gen=_arr(1, 40, -50, 50),
    ),
    Spec(
        slug="count-even-and-odd",
        title="Count Even and Odd",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "The lottery office wants to know how many winning tickets have even numbers and how many have odd numbers.\n\n"
            "Given n ticket numbers, count both."
        ),
        input_format="The first line has n.\nThe second line has n integers.",
        output_format="Print the count of even numbers and the count of odd numbers, separated by a space.",
        constraints=["1 ≤ n ≤ 1000", "-10^6 ≤ value ≤ 10^6"],
        hints=["Use two counters.", "Careful: in some languages -3 % 2 is -1, not 1. Check x % 2 == 0 for even instead."],
        approach=(
            "Scan the array once and increase the right counter.\n\n"
            "Negative numbers are the trap. Testing x % 2 == 0 works in every language, while testing x % 2 == 1 fails for negatives in C, C++ and Java."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
nums = list(map(int, input().split()))
even = 0
odd = 0
for x in nums:
    if x % 2 == 0:
        even += 1
    else:
        odd += 1
print(even, odd)
''',
        samples=[
            ("6\n1 2 3 4 5 6", "Even: 2, 4, 6. Odd: 1, 3, 5."),
            ("4\n-3 -2 0 7", "Even: -2, 0. Odd: -3, 7. Zero is even!"),
            ("3\n11 13 15", "All odd."),
        ],
        edge=[array_input([0]), array_input([-1]), array_input([1000000, -1000000, 999999])],
        gen=_arr(1, 40, -1000, 1000),
    ),
    Spec(
        slug="reverse-the-queue",
        title="Reverse the Queue",
        difficulty="easy",
        tags=["Arrays", "Two Pointers"],
        story=(
            "In the school lunch queue, the teacher says: 'Today the last student goes first!' "
            "Reverse the order of the queue.\n\n"
            "Given n roll numbers, print them in reverse order."
        ),
        input_format="The first line has n.\nThe second line has n integers.",
        output_format="Print the n integers in reverse order, separated by single spaces.",
        constraints=["1 ≤ n ≤ 1000", "-10^9 ≤ value ≤ 10^9"],
        hints=[
            "Loop from the last index (n - 1) down to 0.",
            "Two-pointer way: swap a[left] and a[right], then move both pointers inward.",
        ],
        approach=(
            "The easiest way is to print from the back. The more useful way is in place: swap the first and last, "
            "then the second and second-last, until the pointers meet.\n\n"
            "This is your first two-pointer technique, and it shows up in many later problems."
        ),
        time="O(n)", space="O(1) extra",
        solution='''
n = int(input())
a = list(map(int, input().split()))
left, right = 0, n - 1
while left < right:
    a[left], a[right] = a[right], a[left]
    left += 1
    right -= 1
print(" ".join(map(str, a)))
''',
        samples=[
            ("5\n10 20 30 40 50", "The last student, 50, now comes first."),
            ("1\n7", "One student, nothing to change."),
            ("4\n1 2 2 1", "This queue reads the same both ways."),
        ],
        edge=[array_input([1, 2]), array_input([-1000000000, 1000000000, 0])],
        gen=_arr(1, 40, -1000, 1000),
    ),
    Spec(
        slug="find-the-roll-number",
        title="Find the Roll Number",
        difficulty="easy",
        tags=["Arrays", "Searching"],
        story=(
            "The exam hall list has n roll numbers in the order students are seated. "
            "The invigilator wants to know the seat position of roll number x.\n\n"
            "Print the index (starting from 0) where x appears first, or -1 if x is not in the list."
        ),
        input_format="The first line has n.\nThe second line has n integers.\nThe third line has x.",
        output_format="Print the first index of x (0-based), or -1.",
        constraints=["1 ≤ n ≤ 1000", "1 ≤ values, x ≤ 10^6"],
        hints=[
            "Check each index i. As soon as a[i] == x, print i and stop.",
            "If the loop finishes without finding x, print -1.",
        ],
        approach=(
            "This is linear search: check elements one by one from the start. Stop at the first match, because we want the first position.\n\n"
            "Remember that indexes start at 0 in most programming languages."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
x = int(input())
answer = -1
for i in range(n):
    if a[i] == x:
        answer = i
        break
print(answer)
''',
        samples=[
            ("5\n101 205 150 340 205\n205", "205 is first found at index 1 (the second seat)."),
            ("3\n11 22 33\n44", "44 is not in the list."),
            ("4\n9 8 7 6\n9", "Found right at the start, index 0."),
        ],
        edge=[array_input([5]) + "\n5", array_input([5]) + "\n6", array_input([3, 3, 3]) + "\n3", array_input([1, 2, 3, 4]) + "\n4"],
        gen=_search_case,
    ),
    Spec(
        slug="second-highest-score",
        title="Second Highest Score",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "In the class quiz, the topper gets a gold medal and the second-highest scorer gets silver. "
            "If many students tie, they share the same medal, so we need the second highest distinct score.\n\n"
            "If there is no second distinct score (all scores are the same), print -1."
        ),
        input_format="The first line has n.\nThe second line has n scores.",
        output_format="Print the second highest distinct score, or -1.",
        constraints=["1 ≤ n ≤ 1000", "0 ≤ score ≤ 100"],
        hints=[
            "Keep two variables: first and second. Start both at -1.",
            "When you see a score bigger than first, the old first becomes second. If it is between second and first (not equal to first), update second.",
        ],
        approach=(
            "Sorting works, but a single scan is smarter. Track the best and second-best distinct values.\n\n"
            "When a new maximum arrives, the old maximum slides down to second place. Equal values must be ignored so that ties don't count twice."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
first = -1
second = -1
for x in a:
    if x > first:
        second = first
        first = x
    elif first > x > second:
        second = x
print(second)
''',
        samples=[
            ("5\n78 92 85 92 60", "Highest is 92 (twice). The next distinct score is 85."),
            ("3\n50 50 50", "All equal, so there is no second highest."),
            ("2\n0 100", "100 is first and 0 is second."),
            ("1\n77", "Only one student, so -1."),
        ],
        edge=[array_input([100, 99]), array_input([5, 4, 3, 2, 1]), array_input([1, 2, 3, 4, 5]), array_input([0, 0])],
        gen=_arr(1, 30, 0, 100),
    ),
    Spec(
        slug="is-the-line-sorted",
        title="Is the Line Sorted?",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "For the assembly, students must stand in order of height from shortest to tallest. Equal heights may stand together.\n\n"
            "Given the heights in line order, check whether the line is sorted in non-decreasing order."
        ),
        input_format="The first line has n.\nThe second line has n heights.",
        output_format="Print Yes if the line is sorted, otherwise No.",
        constraints=["1 ≤ n ≤ 1000", "1 ≤ height ≤ 300"],
        hints=["Compare every neighbouring pair a[i] and a[i+1].", "If even one pair has a[i] > a[i+1], the answer is No."],
        approach=(
            "You don't need to sort anything. Just look for a single place where a bigger value comes before a smaller one.\n\n"
            "Comparing neighbours (i and i+1) is a pattern you will use often. Watch the loop boundary so you don't go past the last index."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
ok = True
for i in range(n - 1):
    if a[i] > a[i + 1]:
        ok = False
        break
print("Yes" if ok else "No")
''',
        samples=[
            ("5\n120 125 125 130 140", "Every student is at least as tall as the one before."),
            ("4\n120 135 128 140", "135 comes before 128, so it is not sorted."),
            ("1\n150", "One student is always in order."),
        ],
        edge=[array_input([5, 5, 5]), array_input([2, 1]), array_input([1, 2]), array_input(list(range(1, 300))),
              array_input(list(range(1, 50)) + [1])],
        gen=lambda r: array_input(sorted(rand_list(r, 2, 20, 1, 300))) if r.random() < 0.5 else _arr(2, 20, 1, 300)(r),
    ),
    Spec(
        slug="count-the-votes",
        title="Count the Votes",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "In the class monitor election, each vote is the candidate's number. "
            "Count how many votes candidate x received."
        ),
        input_format="The first line has n, the number of votes.\nThe second line has n integers.\nThe third line has x.",
        output_format="Print the number of votes x received.",
        constraints=["1 ≤ n ≤ 1000", "1 ≤ vote, x ≤ 100"],
        hints=[
            "Use a counter and increase it whenever a[i] == x.",
            "Unlike searching, don't stop at the first match. Every vote must be checked.",
        ],
        approach=(
            "A scan with a counter. Unlike linear search, you must not stop at the first match, because every occurrence counts."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
votes = list(map(int, input().split()))
x = int(input())
count = 0
for v in votes:
    if v == x:
        count += 1
print(count)
''',
        samples=[
            ("7\n1 2 1 3 1 2 1\n1", "Candidate 1 appears 4 times."),
            ("5\n4 4 5 5 6\n7", "Nobody voted for 7."),
            ("3\n9 9 9\n9", "All three votes went to 9."),
        ],
        edge=[array_input([1]) + "\n1", array_input([100] * 1000) + "\n100"],
        gen=lambda r: array_input(rand_list(r, 1, 40, 1, 6)) + f"\n{r.randint(1, 7)}",
    ),
    Spec(
        slug="running-total-of-savings",
        title="Running Total of Savings",
        difficulty="easy",
        tags=["Arrays", "Prefix Sum"],
        story=(
            "Sneha saves some money in her piggy bank every week. "
            "She wants to see how much she has after each week.\n\n"
            "Given the weekly savings, print the running total after each week."
        ),
        input_format="The first line has n.\nThe second line has n integers, the savings each week.",
        output_format="Print n numbers separated by spaces. The i-th number is the total of the first i weeks.",
        constraints=["1 ≤ n ≤ 1000", "0 ≤ saving ≤ 10^4"],
        hints=["Keep a running sum and print it after adding each week.", "This is called a prefix sum."],
        approach=(
            "Each answer equals the previous answer plus the current element. You never need to re-add from the beginning.\n\n"
            "Prefix sums are a powerful trick: later they let you find the sum of any range in O(1)."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
running = 0
result = []
for x in a:
    running += x
    result.append(str(running))
print(" ".join(result))
''',
        samples=[
            ("4\n100 50 0 200", "After week 1: 100, week 2: 150, week 3: 150, week 4: 350."),
            ("1\n500", "Only one week."),
            ("5\n1 1 1 1 1", "1, 2, 3, 4, 5."),
        ],
        edge=[array_input([0, 0, 0]), array_input([10000] * 1000)],
        gen=_arr(1, 30, 0, 10000),
    ),
    Spec(
        slug="rotate-the-playlist",
        title="Rotate the Playlist",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "Your music app plays songs in a circle. When you press 'skip' k times, the first k songs move to the end of the playlist.\n\n"
            "Rotate the array to the left by k positions."
        ),
        input_format="The first line has n and k.\nThe second line has n integers.",
        output_format="Print the rotated array, separated by single spaces.",
        constraints=["1 ≤ n ≤ 1000", "0 ≤ k ≤ 10^9", "-1000 ≤ value ≤ 1000"],
        hints=[
            "Rotating by n brings the array back to the start. So only k % n rotations matter.",
            "The answer is a[k:] followed by a[:k], with k reduced first.",
        ],
        approach=(
            "First reduce k with k % n. This handles huge k without looping a billion times.\n\n"
            "Then the element at new position i comes from old position (i + k) % n. The modulo makes the index wrap around."
        ),
        time="O(n)", space="O(n)",
        solution='''
n, k = map(int, input().split())
a = list(map(int, input().split()))
k = k % n
rotated = []
for i in range(n):
    rotated.append(a[(i + k) % n])
print(" ".join(map(str, rotated)))
''',
        samples=[
            ("5 2\n1 2 3 4 5", "Songs 1 and 2 move to the end."),
            ("3 3\n7 8 9", "Rotating by 3 = full circle, nothing changes."),
            ("4 0\n4 3 2 1", "No skip at all."),
            ("3 1000000000\n10 20 30", "10^9 % 3 = 1, so rotate by just 1."),
        ],
        edge=["1 5\n42", "2 1\n1 2", "6 7\n1 2 3 4 5 6"],
        gen=_rotate_case,
    ),
    Spec(
        slug="move-zeros-to-end",
        title="Move the Zeros to the End",
        difficulty="easy",
        tags=["Arrays", "Two Pointers"],
        story=(
            "A shopkeeper's stock list has some items with 0 quantity. "
            "He wants all the out-of-stock (zero) items moved to the end, while the other items keep their original order.\n\n"
            "Move all zeros to the end."
        ),
        input_format="The first line has n.\nThe second line has n integers.",
        output_format="Print the modified array, separated by single spaces.",
        constraints=["1 ≤ n ≤ 1000", "-1000 ≤ value ≤ 1000"],
        hints=[
            "Keep a pointer pos for where the next non-zero element should go.",
            "Copy every non-zero to a[pos] and increase pos. Fill the rest with zeros.",
        ],
        approach=(
            "Use a 'write pointer'. Scan the array, and every time you see a non-zero, write it at position pos and move pos forward. "
            "After the scan, everything from pos onward becomes 0.\n\n"
            "The relative order of the non-zero items is preserved because you copy them in the order you see them."
        ),
        time="O(n)", space="O(1) extra",
        solution='''
n = int(input())
a = list(map(int, input().split()))
pos = 0
for x in a:
    if x != 0:
        a[pos] = x
        pos += 1
while pos < n:
    a[pos] = 0
    pos += 1
print(" ".join(map(str, a)))
''',
        samples=[
            ("6\n0 1 0 3 12 0", "Non-zero items 1, 3, 12 keep their order, and the zeros go to the end."),
            ("3\n0 0 0", "All zeros, nothing to move."),
            ("4\n5 -2 7 9", "No zeros at all."),
        ],
        edge=[array_input([0]), array_input([1]), array_input([0, 0, 1]), array_input([1, 0, 0])],
        gen=_zeros_case,
    ),
    Spec(
        slug="remove-duplicate-entries",
        title="Remove Duplicate Entries",
        difficulty="easy",
        tags=["Arrays", "Two Pointers"],
        story=(
            "The attendance register is sorted by roll number, but some roll numbers got entered twice by mistake.\n\n"
            "Given the sorted list, print each roll number only once."
        ),
        input_format="The first line has n.\nThe second line has n integers in non-decreasing order.",
        output_format="Print the unique values in order, separated by single spaces.",
        constraints=["1 ≤ n ≤ 1000", "-1000 ≤ value ≤ 1000"],
        hints=[
            "Because the list is sorted, duplicates sit right next to each other.",
            "Keep an element if it is the first one, or different from the element just before it.",
        ],
        approach=(
            "Sorted order makes this easy: a value is new exactly when it differs from its left neighbour. "
            "No extra data structure is needed.\n\n"
            "This is LeetCode #26 in a friendlier form."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
unique = []
for i in range(n):
    if i == 0 or a[i] != a[i - 1]:
        unique.append(str(a[i]))
print(" ".join(unique))
''',
        samples=[
            ("7\n1 1 2 3 3 3 4", "1, 2, 3 and 4 each kept once."),
            ("3\n5 5 5", "Only 5 remains."),
            ("4\n-2 0 3 8", "Already unique, nothing removed."),
        ],
        edge=[array_input([0]), array_input([1, 2]), array_input([-1000] * 3 + [1000] * 3)],
        gen=_sorted_case,
    ),
    Spec(
        slug="missing-roll-number",
        title="The Missing Roll Number",
        difficulty="easy",
        tags=["Arrays", "Math"],
        story=(
            "A class has n students with roll numbers 1 to n. One student is absent today. "
            "The teacher has the jumbled list of the n - 1 students who are present.\n\n"
            "Find the absent student's roll number."
        ),
        input_format="The first line has n.\nThe second line has n - 1 distinct integers from 1 to n.",
        output_format="Print the missing roll number.",
        constraints=["2 ≤ n ≤ 10^5"],
        hints=[
            "The sum 1 + 2 + … + n = n × (n + 1) / 2.",
            "Subtract the sum of the present roll numbers from it.",
        ],
        approach=(
            "Instead of searching for each number, use maths. The full sum is known by formula, "
            "and whatever is missing from the actual sum is the absent roll number.\n\n"
            "One pass, no sorting, no extra memory."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
present = list(map(int, input().split()))
expected = n * (n + 1) // 2
print(expected - sum(present))
''',
        samples=[
            ("5\n3 1 5 2", "1+2+3+4+5 = 15. Present sum = 11. Missing = 4."),
            ("2\n2", "Only roll number 1 is missing."),
            ("4\n1 2 3", "The last roll number is missing."),
        ],
        edge=["3\n3 2", "2\n1"],
        gen=_missing_case,
    ),
    Spec(
        slug="two-sum-shopping",
        title="Two Items, Exact Budget (Two Sum)",
        difficulty="medium",
        tags=["Arrays", "Hashing"],
        story=(
            "Divya has a gift voucher worth exactly target rupees. It must be spent fully on exactly two different items.\n\n"
            "Given the prices, find the indices i and j (0-based, i < j) of the two items whose prices add up to target. "
            "Exactly one such pair exists."
        ),
        input_format="The first line has n.\nThe second line has n prices.\nThe third line has target.",
        output_format="Print i and j separated by a space, with i < j.",
        constraints=["2 ≤ n ≤ 1000", "-10^4 ≤ price, target ≤ 10^4 (negative values are allowed to make it tricky)", "Exactly one valid pair exists."],
        hints=[
            "Brute force: try every pair (i, j) with two loops. That works for n = 1000.",
            "Better: while scanning, store each value's index in a dictionary. For a[j], check if target - a[j] was already seen.",
        ],
        approach=(
            "The brute-force double loop checks about n²/2 pairs. The famous O(n) trick uses a hash map: "
            "for each element, the partner we need is target - a[j]. If we have already seen it, we found the pair.\n\n"
            "This is LeetCode #1, the most famous interview question in the world."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
target = int(input())
seen = {}
for j in range(n):
    need = target - a[j]
    if need in seen:
        print(seen[need], j)
        break
    seen[a[j]] = j
''',
        samples=[
            ("4\n2 7 11 15\n9", "a[0] + a[1] = 2 + 7 = 9."),
            ("3\n3 2 4\n6", "a[1] + a[2] = 2 + 4 = 6. Using 3 twice is not allowed."),
            ("2\n5 5\n10", "Two different items can have the same price."),
        ],
        edge=["5\n-3 4 1 90 10\n7", "6\n1 2 3 4 5 50\n55"],
        gen=_two_sum_case,
    ),
    Spec(
        slug="longest-attendance-streak",
        title="Longest Attendance Streak",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "The attendance record has 1 for present and 0 for absent. "
            "The principal is giving a prize for the longest run of consecutive present days.\n\n"
            "Find the length of the longest run of consecutive 1s."
        ),
        input_format="The first line has n.\nThe second line has n values, each 0 or 1.",
        output_format="Print the length of the longest streak of 1s.",
        constraints=["1 ≤ n ≤ 1000"],
        hints=["Keep a current count. Add 1 on a 1, and reset it to 0 on a 0.", "Track the maximum current count you ever see."],
        approach=(
            "Two variables do the job: the current streak and the best streak. "
            "A 0 breaks the current streak, and each 1 extends it, after which you update the best.\n\n"
            "This 'current versus best' idea leads directly to Kadane's algorithm later."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
current = 0
best = 0
for x in a:
    if x == 1:
        current += 1
        best = max(best, current)
    else:
        current = 0
print(best)
''',
        samples=[
            ("8\n1 1 0 1 1 1 0 1", "The longest run is the three 1s in the middle."),
            ("3\n0 0 0", "Never present, so 0."),
            ("4\n1 1 1 1", "Present every day: 4."),
        ],
        edge=[array_input([1]), array_input([0]), array_input([0, 1]), array_input([1, 0])],
        gen=_bits_case,
    ),
    Spec(
        slug="leaders-in-the-line",
        title="Leaders in the Line",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "Students stand in a row facing right. A student is a leader if they are strictly taller than everyone standing to their right. "
            "The last student is always a leader.\n\n"
            "Print all leaders in the order they stand."
        ),
        input_format="The first line has n.\nThe second line has n heights.",
        output_format="Print the leaders in their original order, separated by single spaces.",
        constraints=["1 ≤ n ≤ 1000", "1 ≤ height ≤ 1000"],
        hints=[
            "Scan from the right end and keep the maximum seen so far.",
            "An element is a leader if it is greater than that maximum. Reverse the collected leaders at the end.",
        ],
        approach=(
            "Checking everyone to the right for each student is O(n²). "
            "Walking from the right instead, you only need to know the tallest student seen so far.\n\n"
            "Scanning from the other end is a simple but powerful change of viewpoint."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
leaders = []
best = 0
for i in range(n - 1, -1, -1):
    if a[i] > best:
        leaders.append(a[i])
        best = a[i]
leaders.reverse()
print(" ".join(map(str, leaders)))
''',
        samples=[
            ("6\n16 17 4 3 5 2", "17 is taller than everyone after it, 5 beats 2, and 2 is last."),
            ("4\n1 2 3 4", "Only the last student is a leader."),
            ("4\n9 7 5 3", "Every student is taller than all to their right."),
        ],
        edge=[array_input([5]), array_input([5, 5, 5]), array_input([1000, 1, 1000])],
        gen=_arr(1, 25, 1, 100),
    ),
    Spec(
        slug="merge-two-sorted-lists",
        title="Merge Two Sorted Lists",
        difficulty="easy",
        tags=["Arrays", "Two Pointers", "Sorting"],
        story=(
            "Two sections of a class have their marks lists, each already sorted. The teacher wants one combined sorted list.\n\n"
            "Merge the two sorted arrays into one sorted array without sorting from scratch."
        ),
        input_format="The first line has n and m.\nThe second line has n sorted integers.\nThe third line has m sorted integers.",
        output_format="Print the merged sorted list, separated by single spaces.",
        constraints=["1 ≤ n, m ≤ 1000", "-10^4 ≤ value ≤ 10^4"],
        hints=[
            "Use two pointers i and j, one in each list. Pick the smaller of a[i] and b[j] and move that pointer.",
            "When one list is finished, copy the rest of the other list.",
        ],
        approach=(
            "Both lists are sorted, so the smallest remaining value is always at the front of one of them. "
            "Compare the two fronts, take the smaller, and advance.\n\n"
            "This merge step is the heart of merge sort, one of the most important sorting algorithms."
        ),
        time="O(n + m)", space="O(n + m)",
        solution='''
n, m = map(int, input().split())
a = list(map(int, input().split()))
b = list(map(int, input().split()))
i = j = 0
merged = []
while i < n and j < m:
    if a[i] <= b[j]:
        merged.append(a[i])
        i += 1
    else:
        merged.append(b[j])
        j += 1
merged.extend(a[i:])
merged.extend(b[j:])
print(" ".join(map(str, merged)))
''',
        samples=[
            ("3 4\n1 4 9\n2 3 10 12", "Pick the smaller front each time: 1, 2, 3, 4, 9, 10, 12."),
            ("2 2\n5 5\n5 5", "Equal values are all kept."),
            ("1 3\n100\n1 2 3", "The second list finishes first, then 100 is copied."),
        ],
        edge=["1 1\n-1\n1", "1 1\n7\n7"],
        gen=_merge_case,
    ),
    Spec(
        slug="gold-price-trading",
        title="Best Day to Buy and Sell Gold",
        difficulty="easy",
        tags=["Arrays", "Greedy"],
        story=(
            "Ritu tracked the price of 1 gram of gold for n days. She can buy once and sell once later "
            "(selling must happen after buying).\n\n"
            "Find the maximum profit she can make. If no profit is possible, print 0."
        ),
        input_format="The first line has n.\nThe second line has n prices.",
        output_format="Print the maximum profit.",
        constraints=["1 ≤ n ≤ 10^5", "1 ≤ price ≤ 10^4"],
        hints=[
            "For each day, the best buying price is the minimum price seen before that day.",
            "Keep the minimum so far, and update the best profit with price - minimum.",
        ],
        approach=(
            "Trying all buy and sell pairs is O(n²). The clever part: if you sell today, you should have bought at the cheapest day before today. "
            "So keep the minimum price so far and check today's profit against it.\n\n"
            "This is LeetCode #121, a classic one-pass greedy solution."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
prices = list(map(int, input().split()))
min_price = prices[0]
best = 0
for p in prices:
    if p < min_price:
        min_price = p
    if p - min_price > best:
        best = p - min_price
print(best)
''',
        samples=[
            ("6\n7 1 5 3 6 4", "Buy at 1 (day 2) and sell at 6 (day 5): profit 5."),
            ("5\n7 6 4 3 1", "Prices only fall, so don't trade: 0."),
            ("2\n1 2", "Buy at 1, sell at 2."),
        ],
        edge=[array_input([5]), array_input([3, 3, 3]), array_input([2, 10, 1, 4]), array_input([10000, 1, 10000])],
        gen=_arr(1, 30, 1, 100),
    ),
    Spec(
        slug="maximum-subarray-sum",
        title="Best Run of Days (Maximum Subarray Sum)",
        difficulty="medium",
        tags=["Arrays", "Kadane's Algorithm"],
        story=(
            "A small shop records its daily profit (negative means loss). "
            "The owner wants to find the best stretch of consecutive days, the one with the biggest total profit.\n\n"
            "Find the maximum sum of any non-empty contiguous subarray."
        ),
        input_format="The first line has n.\nThe second line has n integers.",
        output_format="Print the maximum subarray sum.",
        constraints=["1 ≤ n ≤ 10^5", "-10^4 ≤ value ≤ 10^4"],
        hints=[
            "At each day, decide: is it better to continue the previous stretch, or start fresh from today?",
            "current = max(a[i], current + a[i]), and best = max(best, current).",
        ],
        approach=(
            "Kadane's algorithm: if the running sum becomes worse than starting fresh, drop it. "
            "Each element either extends the best stretch ending at the previous day, or starts a new one.\n\n"
            "Start best with the first element so that an all-negative array works. "
            "This is LeetCode #53, and it builds on the attendance streak idea."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
current = a[0]
best = a[0]
for i in range(1, n):
    current = max(a[i], current + a[i])
    best = max(best, current)
print(best)
''',
        samples=[
            ("9\n-2 1 -3 4 -1 2 1 -5 4", "The stretch 4, -1, 2, 1 gives 6."),
            ("3\n-5 -1 -8", "All losses: the best is the smallest loss, -1."),
            ("4\n5 4 -1 7", "Take everything: 5 + 4 - 1 + 7 = 15."),
        ],
        edge=[array_input([7]), array_input([-7]), array_input([0, 0, 0]), array_input([10000] * 50)],
        gen=_arr(1, 30, -50, 50),
    ),
    Spec(
        slug="attendance-frequency",
        title="How Many Times Each? (Frequency Count)",
        difficulty="easy",
        tags=["Arrays", "Hashing"],
        story=(
            "A juice shop recorded the flavour number of every glass sold today. "
            "The owner wants to know how many glasses of each flavour were sold.\n\n"
            "Print each distinct value with its count, in the order the values first appeared."
        ),
        input_format="The first line has n.\nThe second line has n integers.",
        output_format="For each distinct value (in first-appearance order), print a line: <value> <count>",
        constraints=["1 ≤ n ≤ 1000", "1 ≤ value ≤ 10^9"],
        hints=[
            "Use a dictionary (hash map) from value to count.",
            "To keep the first-appearance order, also keep a list of values in the order you first saw them.",
        ],
        approach=(
            "A hash map counts things in O(1) per element. Each time you see a value, increase its count. "
            "The first time you see it, also note it in an order list.\n\n"
            "Counting with a map is one of the most useful tools in DSA. Many problems become simple once you have the counts."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
count = {}
order = []
for x in a:
    if x not in count:
        count[x] = 0
        order.append(x)
    count[x] += 1
for x in order:
    print(x, count[x])
''',
        samples=[
            ("7\n3 1 3 2 1 3 5", "Flavour 3 sold 3 times, 1 twice, 2 once and 5 once."),
            ("3\n8 8 8", "Only one flavour."),
            ("4\n4 3 2 1", "All different, each sold once."),
        ],
        edge=[array_input([1]), array_input([1000000000, 1, 1000000000])],
        gen=_arr(1, 30, 1, 8),
    ),
    Spec(
        slug="common-friends",
        title="Common Friends",
        difficulty="easy",
        tags=["Arrays", "Hashing", "Sorting"],
        story=(
            "Rahul and Neha each have a list of friend IDs (some IDs may be repeated by mistake). "
            "Find the friends they have in common.\n\n"
            "Print the common IDs in increasing order, each only once. If there are none, print None."
        ),
        input_format="The first line has n and m.\nThe second line has n IDs (Rahul).\nThe third line has m IDs (Neha).",
        output_format="Print the common IDs in increasing order separated by spaces, or None.",
        constraints=["1 ≤ n, m ≤ 1000", "1 ≤ ID ≤ 10^6"],
        hints=["Put Rahul's IDs in a set.", "Check each of Neha's IDs against it, avoid repeats, then sort the result."],
        approach=(
            "A set answers 'is this present?' in O(1). Build a set from the first list, and keep the IDs from the second list that are in it. "
            "Collecting them in another set removes duplicates, and sorting gives the required order."
        ),
        time="O((n + m) log(n + m))", space="O(n + m)",
        solution='''
n, m = map(int, input().split())
a = list(map(int, input().split()))
b = list(map(int, input().split()))
first = set(a)
common = set()
for x in b:
    if x in first:
        common.add(x)
if common:
    print(" ".join(map(str, sorted(common))))
else:
    print("None")
''',
        samples=[
            ("5 4\n4 9 5 4 1\n9 4 9 8", "4 and 9 are in both lists."),
            ("3 3\n1 2 3\n4 5 6", "Nothing in common."),
            ("2 3\n7 7\n7 7 7", "7 is common, and is printed once."),
        ],
        edge=["1 1\n1\n1", "1 1\n1\n2"],
        gen=_two_arrays,
    ),
    Spec(
        slug="kids-with-the-most-chocolates",
        title="Kids With the Most Chocolates",
        difficulty="easy",
        tags=["Arrays"],
        story=(
            "Each kid at a birthday party has some chocolates. You have extra chocolates to give, all to one kid.\n\n"
            "For each kid, find out whether, after receiving all the extra chocolates, they would have the most chocolates (ties count as most)."
        ),
        input_format="The first line has n.\nThe second line has n integers (chocolates each kid has).\nThe third line has extra.",
        output_format="Print n words separated by spaces: Yes or No for each kid.",
        constraints=["1 ≤ n ≤ 100", "1 ≤ chocolates ≤ 100", "1 ≤ extra ≤ 50"],
        hints=["Find the current maximum first.", "Kid i says Yes if a[i] + extra >= maximum."],
        approach=(
            "Two passes: first find the maximum, then compare each kid's possible total against it. "
            "There's no need to try giving the chocolates to everyone one by one.\n\n"
            "This is LeetCode #1431, a nice example of computing something once and reusing it."
        ),
        time="O(n)", space="O(n)",
        solution='''
n = int(input())
a = list(map(int, input().split()))
extra = int(input())
top = max(a)
answer = []
for x in a:
    answer.append("Yes" if x + extra >= top else "No")
print(" ".join(answer))
''',
        samples=[
            ("5\n2 3 5 1 3\n3", "Max is 5. Kids with 2, 3, 5, 3 can reach 5 or more. The kid with 1 reaches only 4."),
            ("3\n4 2 1\n1", "Only the kid with 4 can be the top."),
            ("2\n10 10\n1", "Both already share the top."),
        ],
        edge=["1\n1\n1", "3\n1 100 1\n50"],
        gen=_candies_case,
    ),
]
